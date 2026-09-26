"""Render the reviewed SQLAlchemy model into the CLI-created migration file."""
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from .db import metadata


def render():
    dialect = postgresql.dialect()
    parts = ["-- Lectic invited pilot. Apply only to its dedicated Supabase project.", "BEGIN;"]
    for table in metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect))+";")
        for index in table.indexes: parts.append(str(CreateIndex(index).compile(dialect=dialect))+";")
        name = table.name
        parts += [f"ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY;",
                  f"REVOKE ALL ON public.{name} FROM anon, authenticated;"]
        if "owner" in table.c:
            parts.append(f"CREATE POLICY owner_read ON public.{name} FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);")
        elif name == "pilot_accounts":
            parts.append(f"CREATE POLICY own_account ON public.{name} FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = id);")
        # API-only writes: authenticated clients cannot forge jobs, budget entries or quota usage.
    parts += ["INSERT INTO storage.buckets (id, name, public, file_size_limit) VALUES ('lectic-private', 'lectic-private', false, 536870912) ON CONFLICT (id) DO NOTHING;",
              "CREATE POLICY lectic_owner_download ON storage.objects FOR SELECT TO authenticated USING (bucket_id = 'lectic-private' AND (storage.foldername(name))[1] = (SELECT auth.uid())::text);",
              "-- Uploads are accepted only through the API, which enforces invitations and quota.",
              "COMMIT;"]
    return "\n".join(line.rstrip() for line in "\n\n".join(parts).splitlines())+"\n"


if __name__ == '__main__':
    import sys
    from pathlib import Path
    Path(sys.argv[1]).write_text(render(), encoding='utf-8')
