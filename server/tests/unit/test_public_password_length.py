import pytest
from pydantic import ValidationError
from szyg.api.cloud_routes import ActivateBody, ChangePasswordBody, LoginBody, RegisterBody


@pytest.mark.parametrize(("model", "field", "other"), [
    (ActivateBody, "password", {"invitation_code": "invite", "display_name": "User"}),
    (RegisterBody, "password", {"email": "member@example.com", "display_name": "User", "verification_id": "abcdefgh", "verification_code": "123456"}),
    (ChangePasswordBody, "new_password", {"email": "member@example.com", "verification_id": "abcdefgh", "verification_code": "123456"}),
])
def test_new_public_passwords_have_a_six_character_minimum(model, field, other):
    with pytest.raises(ValidationError):
        model(**other, **{field: "12345"})
    for password in ("123456", "新密码六字符", "original long password"):
        assert getattr(model(**other, **{field: password}), field) == password


def test_sign_in_passes_existing_password_verbatim():
    for value in ("short", "  old password  ", "original長密码"):
        assert LoginBody(email="member@example.com", password=value).password == value
