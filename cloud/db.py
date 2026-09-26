"""Durable operations, leases and an atomic, pessimistic spending ledger."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import time
from uuid import uuid4
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, BigInteger,
                        Float, JSON, Text, UniqueConstraint, select, update, event, func)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()


def table(name, *cols, owned=True):
    return Table("pilot_" + name, metadata, Column("id", String(64), primary_key=True),
                 *([Column("owner", String(36), nullable=False, index=True)] if owned else []),
                 Column("created", Float, nullable=False, default=time.time), *cols)


accounts = table("accounts", Column("email", Text, nullable=False), Column("used_bytes", BigInteger, default=0, nullable=False),
                 Column("lease", String(64)), Column("lease_until", Float, default=0, nullable=False), owned=False)
invites = table("invites", Column("enabled", Integer, nullable=False, default=1), owned=False)
jobs = table("jobs", Column("kind", String(32), nullable=False), Column("status", String(24), nullable=False),
             Column("payload", JSON, nullable=False), Column("result", JSON), Column("error", Text),
             Column("priority", Integer, nullable=False), Column("attempts", Integer, default=0, nullable=False),
             Column("available", Float, default=0, nullable=False), Column("lease_until", Float, default=0, nullable=False),
             Column("cancelled", Integer, default=0, nullable=False), Column("key", String(64), nullable=False),
             Column("fingerprint", String(64), nullable=False), UniqueConstraint("owner", "key"))
captures = table("captures", Column("title", Text, nullable=False), Column("state", String(24), nullable=False),
                 Column("data", JSON, nullable=False), Column("bytes", BigInteger, default=0, nullable=False))
packs = table("packs", Column("title", Text, nullable=False), Column("data", JSON, nullable=False))
results = table("results", Column("title", Text, nullable=False), Column("data", JSON, nullable=False))
backups = table("backups", Column("data", JSON, nullable=False))
shares = table("shares", Column("token_hash", String(64), unique=True, nullable=False),
               Column("revoked", Integer, default=0, nullable=False), Column("data", JSON, nullable=False))
calls = table("calls", Column("status", String(24), nullable=False), Column("reserved", BigInteger, nullable=False),
              Column("actual", BigInteger), Column("month", String(7), nullable=False), Column("data", JSON))
budgets = table("budgets", Column("committed", BigInteger, nullable=False, default=0), owned=False)
events = table("events", Column("name", String(40), nullable=False), Column("data", JSON, nullable=False))


def uid(): return str(uuid4())
def hash_json(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Conflict(Exception): pass
class SpendingLimit(Exception): pass
class UncertainCall(Exception): pass
class YieldJob(Exception): pass


class Database:
    def __init__(self, settings):
        self.settings = settings
        self.engine = create_engine(settings.db_url, pool_pre_ping=True,
                                    connect_args={"check_same_thread": False, "timeout": 30} if settings.db_url.startswith("sqlite") else {})
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def pragmas(db, _):
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA busy_timeout=30000")

    def initialize(self):
        if not self.settings.dev and self.engine.dialect.name != "postgresql":
            raise ValueError("Production requires PostgreSQL.")
        metadata.create_all(self.engine)

    @contextmanager
    def transaction(self):
        with self.engine.connect() as c:
            if self.engine.dialect.name == "sqlite": c.exec_driver_sql("BEGIN IMMEDIATE")
            else: c.begin()
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def get(self, tab, ident, owner=None):
        q = select(tab).where(tab.c.id == ident)
        if owner is not None: q = q.where(tab.c.owner == owner)
        with self.engine.connect() as c:
            row = c.execute(q).mappings().first()
            return dict(row) if row else None

    def listing(self, tab, owner):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(tab).where(tab.c.owner == owner).order_by(tab.c.created.desc()).limit(200)).mappings()]

    def mutate(self, tab, ident, owner, **values):
        with self.transaction() as c:
            return c.execute(update(tab).where(tab.c.id == ident, tab.c.owner == owner).values(**values)).rowcount

    def enqueue(self, owner, kind, payload, key, priority=5, connection=None):
        fingerprint = hash_json({"kind": kind, "payload": payload})
        def insert(c):
            old = c.execute(select(jobs).where(jobs.c.owner == owner, jobs.c.key == key)).mappings().first()
            if old:
                if old["fingerprint"] != fingerprint: raise Conflict("This retry key belongs to a different request.")
                return dict(old)
            pending = c.execute(select(func.count()).select_from(jobs).where(jobs.c.owner == owner,
                        jobs.c.status.in_(["saved", "processing", "awaiting_upload"]))).scalar_one()
            if pending >= 50: raise Conflict("Your pending queue is full. Finish or cancel some saves first.")
            record = dict(id=uid(), owner=owner, kind=kind, payload=payload, key=key, fingerprint=fingerprint,
                          priority=priority, status="saved", created=time.time(), attempts=0, available=0, lease_until=0, cancelled=0)
            c.execute(jobs.insert().values(**record))
            return record
        if connection is not None: return insert(connection)
        with self.transaction() as c:
            # Account lock also serializes idempotency-key insertion on PostgreSQL.
            c.execute(select(accounts.c.id).where(accounts.c.id == owner).with_for_update()).first()
            return insert(c)

    def claim(self):
        now = time.time()
        with self.transaction() as c:
            expired = c.execute(select(jobs).where(jobs.c.status == "processing", jobs.c.lease_until < now,
                                (jobs.c.attempts >= 3) | (jobs.c.cancelled == 1)).with_for_update()).mappings().all()
            for old in expired:
                c.execute(update(jobs).where(jobs.c.id == old["id"]).values(
                    status="cancelled" if old["cancelled"] else "failed", lease_until=0,
                    error="Processing stopped. Saved work is safe."))
                if old["kind"] == "capture":
                    c.execute(update(captures).where(captures.c.id == old["payload"]["capture_id"],
                        captures.c.owner == old["owner"], captures.c.state == "processing").values(state="saved"))
                c.execute(update(accounts).where(accounts.c.id == old["owner"], accounts.c.lease == old["id"]).values(lease=None, lease_until=0))
            # Exclude busy homes before the limit so one account's backlog cannot hide another's work.
            candidates = c.execute(select(jobs).join(accounts, accounts.c.id == jobs.c.owner).where(
                accounts.c.lease_until < now, jobs.c.cancelled == 0, jobs.c.attempts < 3,
                jobs.c.status.in_(["saved", "processing"]), jobs.c.available <= now, jobs.c.lease_until < now)
                .order_by(jobs.c.priority, jobs.c.created).limit(20).with_for_update(of=jobs, skip_locked=True)).mappings().all()
            for job in candidates:
                owner = job["owner"]
                acquired = c.execute(update(accounts).where(accounts.c.id == owner, accounts.c.lease_until < now)
                                     .values(lease=job["id"], lease_until=now + 90)).rowcount
                if acquired:
                    c.execute(update(jobs).where(jobs.c.id == job["id"]).values(status="processing", attempts=job["attempts"]+1, lease_until=now+90))
                    return dict(job)
        return None

    def heartbeat(self, job):
        with self.transaction() as c:
            c.execute(update(accounts).where(accounts.c.id == job["owner"], accounts.c.lease == job["id"]).values(lease_until=time.time()+90))
            c.execute(update(jobs).where(jobs.c.id == job["id"]).values(lease_until=time.time()+90))

    def yield_job(self, job):
        with self.transaction() as c:
            c.execute(update(jobs).where(jobs.c.id == job["id"]).values(status="saved", lease_until=0,
                       available=0, attempts=jobs.c.attempts-1))
            c.execute(update(accounts).where(accounts.c.id == job["owner"], accounts.c.lease == job["id"]).values(lease=None, lease_until=0))

    def prioritize_creation(self, owner, job_id):
        if not job_id: return
        with self.engine.connect() as c:
            job = c.execute(select(jobs).where(jobs.c.id == job_id, jobs.c.owner == owner)).mappings().one()
            if job["cancelled"]: raise ValueError("Operation cancelled")
            waiting = c.execute(select(jobs.c.id).where(jobs.c.owner == owner, jobs.c.status == "saved",
                       jobs.c.cancelled == 0, jobs.c.priority < job["priority"]).limit(1)).first()
        if waiting: raise YieldJob("A creation is waiting; resume this operation from its checkpoints afterward.")

    def finish(self, job, result=None, error=None, retry=False):
        with self.transaction() as c:
            row = c.execute(select(jobs).where(jobs.c.id == job["id"])).mappings().one()
            status = "cancelled" if row["cancelled"] else "saved" if retry and row["attempts"] < 3 else "failed" if error else "complete"
            c.execute(update(jobs).where(jobs.c.id == job["id"]).values(status=status, result=result, error=error,
                       lease_until=0, available=time.time()+15*row["attempts"]))
            if row["kind"] == "capture" and status in {"saved", "failed", "cancelled"}:
                c.execute(update(captures).where(captures.c.id == row["payload"]["capture_id"],
                           captures.c.owner == row["owner"], captures.c.state == "processing").values(state="saved"))
            c.execute(update(accounts).where(accounts.c.id == job["owner"], accounts.c.lease == job["id"]).values(lease=None, lease_until=0))

    def reserve(self, owner, call_id, estimate):
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        # Ensure the unique month row outside the reservation transaction.
        try:
            with self.engine.begin() as c: c.execute(budgets.insert().values(id=month, committed=0))
        except IntegrityError: pass
        with self.transaction() as c:
            c.execute(select(budgets).where(budgets.c.id == month).with_for_update()).first()
            prior = c.execute(select(calls).where(calls.c.id == call_id, calls.c.owner == owner)).mappings().first()
            if prior:
                if prior["status"] == "complete": return prior["data"]
                raise UncertainCall("A previous paid request has an uncertain outcome. Its reservation is retained; an operator must reconcile it before retrying.")
            allowed = c.execute(update(budgets).where(budgets.c.id == month,
                budgets.c.committed + estimate <= self.settings.monthly_microdollars).values(committed=budgets.c.committed+estimate)).rowcount
            if not allowed: raise SpendingLimit("This month's processing allowance is used. Existing work and downloads remain available.")
            c.execute(calls.insert().values(id=call_id, owner=owner, status="reserved", reserved=estimate, month=month))
        return None

    def settle(self, owner, call_id, actual, data):
        with self.transaction() as c:
            row = c.execute(select(calls).where(calls.c.id == call_id, calls.c.owner == owner).with_for_update()).mappings().one()
            if row["status"] == "complete": return
            c.execute(update(budgets).where(budgets.c.id == row["month"]).values(committed=budgets.c.committed-row["reserved"]+actual))
            c.execute(update(calls).where(calls.c.id == call_id).values(status="complete", actual=actual, data=data))
