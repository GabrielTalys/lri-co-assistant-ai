from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.domain.canvas_keys import CANVAS_KEYS, CANVAS_PROMPT_TEMPLATES, CANVAS_TITLES
from app.models import CanvasQuestion, User


DEFAULT_USER_EMAIL = 'researcher@example.com'
DEFAULT_USER_PASSWORD = 'researcher123'


def seed_user(db) -> None:
    existing = db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
    if existing:
        return
    user = User(email=DEFAULT_USER_EMAIL, password_hash=get_password_hash(DEFAULT_USER_PASSWORD))
    db.add(user)


def seed_canvas_questions(db) -> None:
    existing_questions = {
        question.key: question
        for question in db.scalars(select(CanvasQuestion)).all()
    }
    for key in CANVAS_KEYS:
        title = CANVAS_TITLES.get(key, key.replace('_', ' ').title())
        prompt_template = CANVAS_PROMPT_TEMPLATES.get(
            key,
            f'Provide content for {key.replace("_", " ")}.',
        )
        existing = existing_questions.get(key)
        if existing:
            existing.title = title
            existing.prompt_template = prompt_template
            continue
        db.add(
            CanvasQuestion(
                key=key,
                title=title,
                prompt_template=prompt_template,
            )
        )


def seed() -> None:
    with SessionLocal() as db:
        seed_user(db)
        seed_canvas_questions(db)
        db.commit()


if __name__ == '__main__':
    seed()
