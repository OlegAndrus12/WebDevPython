from passlib.context import CryptContext



class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)


auth_service = AuthService()