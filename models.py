# models.py
import aiosqlite
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# models.py
class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    async def get(user_id):
        async with aiosqlite.connect('articles.db') as db:
            async with db.execute('SELECT id, username, email, password_hash FROM users WHERE id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(*row)
        return None

    @staticmethod
    async def find_by_username(username):
        async with aiosqlite.connect('articles.db') as db:
            async with db.execute('SELECT id, username, email, password_hash FROM users WHERE username = ?', (username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(*row)
        return None

    @staticmethod
    async def create(username, email, password):
        password_hash = generate_password_hash(password)
        async with aiosqlite.connect('articles.db') as db:
            try:
                await db.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', (username, email, password_hash))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

