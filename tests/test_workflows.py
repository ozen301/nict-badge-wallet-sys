import unittest
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.blockchain.api import ChainClient
from nictbw.models import Admin, Base, NFTDefinition, NFTInstance, NFTTemplate, User
from nictbw.workflows import create_and_issue_nft, register_user


class DummyClient(ChainClient):
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    def signup_user(
        self,
        username: str,
        email: str,
        password: str,
        profile_pic_filepath: Optional[str] = None,
        group: Optional[str] = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "username": username,
                "email": email,
                "password": password,
                "profile_pic_filepath": profile_pic_filepath,
                "group": group,
            }
        )
        return self.response


class RegisterUserWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def tearDown(self):
        self.engine.dispose()

    def test_register_user_populates_paymail(self):
        client = DummyClient(
            {
                "status": "success",
                "paymail": "acooluser@bsvapi01.zelowa.com",
                "message": "Registered successfully.",
            }
        )

        with self.Session.begin() as session:
            user = User(in_app_id="in-app-123", paymail=None, nickname="Tester")
            register_user(
                session,
                user,
                password="securepassword",
                email="anemail@example.com",
                username="acooluser",
                client=client,
            )
            self.assertEqual(user.paymail, "acooluser@bsvapi01.zelowa.com")
            self.assertIsNotNone(user.id)

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["username"], "acooluser")
        self.assertEqual(client.calls[0]["password"], "securepassword")
        self.assertEqual(client.calls[0]["email"], "anemail@example.com")

    def test_register_user_requires_paymail_in_response(self):
        client = DummyClient({"status": "success", "message": "missing paymail"})

        with self.Session.begin() as session:
            user = User(in_app_id="user-no-paymail", paymail=None)
            with self.assertRaises(ValueError):
                register_user(
                    session,
                    user,
                    password="securepassword",
                    email="user@example.com",
                    client=client,
                )

        self.assertEqual(len(client.calls), 1)

    def test_register_user_uses_in_app_id_as_default_username(self):
        client = DummyClient({"status": "error", "message": "username taken"})

        with self.Session.begin() as session:
            user = User(in_app_id="fallback-user", paymail=None)
            with self.assertRaises(RuntimeError):
                register_user(
                    session,
                    user,
                    password="securepassword",
                    email="user@example.com",
                    client=client,
                )

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["username"], "fallback-user")


class CreateAndIssueNFTWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def tearDown(self):
        self.engine.dispose()

    def test_returns_instance_for_definition_input(self):
        with self.Session.begin() as session:
            admin = Admin(email="wf-admin@example.com", password_hash="x")
            user = User(in_app_id="wf-user", paymail="wf-user@wallet")
            session.add_all([admin, user])
            session.flush()
            definition = NFTDefinition(
                prefix="WF",
                shared_key="wf-key",
                name="WF NFT",
                nft_type="default",
                created_by_admin_id=admin.id,
            )
            session.add(definition)
            session.flush()

            instance = create_and_issue_nft(
                session=session,
                user=user,
                shared_key=None,
                definition_or_template=definition,
            )

            self.assertIsInstance(instance, NFTInstance)
            self.assertEqual(instance.user_id, user.id)
            self.assertEqual(instance.definition_id, definition.id)
            self.assertEqual(len(user.nfts), 1)
            self.assertEqual(user.nfts[0].id, instance.id)

    def test_template_input_requires_shared_key(self):
        with self.Session.begin() as session:
            admin = Admin(email="wf-admin-template@example.com", password_hash="x")
            user = User(in_app_id="wf-user-template", paymail="wf-user-template@wallet")
            session.add_all([admin, user])
            session.flush()
            template = NFTTemplate(
                prefix="WFT",
                name="WF Template",
                category="event",
                created_by_admin_id=admin.id,
            )
            session.add(template)
            session.flush()

            with self.assertRaises(ValueError):
                create_and_issue_nft(
                    session=session,
                    user=user,
                    shared_key=None,
                    definition_or_template=template,
                )

    def test_template_input_returns_instance(self):
        with self.Session.begin() as session:
            admin = Admin(email="wf-admin-template2@example.com", password_hash="x")
            user = User(in_app_id="wf-user-template2", paymail="wf-user-template2@wallet")
            session.add_all([admin, user])
            session.flush()
            template = NFTTemplate(
                prefix="WFT2",
                name="WF Template 2",
                category="event",
                created_by_admin_id=admin.id,
            )
            session.add(template)
            session.flush()

            instance = create_and_issue_nft(
                session=session,
                user=user,
                shared_key="wf-shared-key",
                definition_or_template=template,
            )

            self.assertIsInstance(instance, NFTInstance)
            self.assertEqual(instance.user_id, user.id)
            self.assertEqual(instance.definition.template_id, template.id)


if __name__ == "__main__":
    unittest.main()
