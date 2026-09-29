"""Unit tests for AccountStore, authentication, token verification, and OAuth."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from account_service import AccountStore, AuthenticationError, AuthorizationError, AccountError


class AccountServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.accounts = AccountStore(self.root)

    def test_create_account_and_authenticate(self):
        acc = self.accounts.create_account('alice@example.com', 'password123', 'Alice')
        self.assertEqual(acc['email'], 'alice@example.com')
        self.assertEqual(acc['display_name'], 'Alice')
        self.assertTrue(acc['account_id'].startswith('acc-'))
        self.assertTrue(Path(acc['home_dir']).exists())

        # Authenticate with right and wrong passwords
        authed = self.accounts.authenticate('alice@example.com', 'password123')
        self.assertEqual(authed['account_id'], acc['account_id'])

        with self.assertRaises(AuthenticationError):
            self.accounts.authenticate('alice@example.com', 'wrongpassword')

        with self.assertRaises(AuthenticationError):
            self.accounts.authenticate('bob@example.com', 'password123')

        # Duplicate email rejected
        with self.assertRaises(AccountError):
            self.accounts.create_account('alice@example.com', 'anotherpassword')

    def test_token_lifecycle_and_verification(self):
        acc = self.accounts.create_account('bob@example.com', 'password123', 'Bob')
        tok = self.accounts.create_access_token(acc['account_id'], client_name='Codex Client')
        token_str = tok['token']

        # Verify token returns the account_id
        verified_id = self.accounts.verify_token(token_str)
        self.assertEqual(verified_id, acc['account_id'])

        # Works with "Bearer " prefix
        self.assertEqual(self.accounts.verify_token(f'Bearer {token_str}'), acc['account_id'])

        # Invalid token raises AuthenticationError
        with self.assertRaises(AuthenticationError):
            self.accounts.verify_token('lectic_tok_invalid_123')

        # Revoke token
        revoked = self.accounts.revoke_token(token_str, account_id=acc['account_id'])
        self.assertTrue(revoked)

        with self.assertRaises(AuthenticationError):
            self.accounts.verify_token(token_str)

    def test_oauth_authorization_code_flow_with_pkce(self):
        import base64
        import hashlib

        acc = self.accounts.create_account('carol@example.com', 'password123', 'Carol')
        verifier = 'high-entropy-cryptographic-code-verifier-string-12345'
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')

        code = self.accounts.create_authorization_code(
            account_id=acc['account_id'],
            client_id='chatgpt',
            redirect_uri='https://chatgpt.com/aip/plugin/oauth/callback',
            code_challenge=challenge,
            code_challenge_method='S256'
        )
        self.assertTrue(code.startswith('code_'))

        # Wrong verifier fails
        with self.assertRaises(AuthenticationError):
            self.accounts.exchange_authorization_code(
                code=code,
                client_id='chatgpt',
                redirect_uri='https://chatgpt.com/aip/plugin/oauth/callback',
                code_verifier='wrong-verifier'
            )

        # Right verifier succeeds
        token_res = self.accounts.exchange_authorization_code(
            code=code,
            client_id='chatgpt',
            redirect_uri='https://chatgpt.com/aip/plugin/oauth/callback',
            code_verifier=verifier
        )
        self.assertIn('access_token', token_res)
        self.assertEqual(token_res['account_id'], acc['account_id'])

        # Code cannot be reused
        with self.assertRaises(AuthenticationError):
            self.accounts.exchange_authorization_code(
                code=code,
                client_id='chatgpt',
                redirect_uri='https://chatgpt.com/aip/plugin/oauth/callback',
                code_verifier=verifier
            )


if __name__ == '__main__':
    unittest.main()
