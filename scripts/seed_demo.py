from pathlib import Path

from app.db.session import Base, SessionLocal, engine
from app.models import File, Job, JobStatus, PageResult, StructuredResult, User


def main() -> None:
    Base.metadata.create_all(bind=engine)
    storage = Path("./storage/uploads/demo")
    storage.mkdir(parents=True, exist_ok=True)
    sample = storage / "demo.md"
    sample.write_text("# Demo document\n\nThis file backs the seeded OCR result.\n", encoding="utf-8")

    with SessionLocal() as db:
        user = db.query(User).filter_by(email="demo@docflow.local").one_or_none()
        if not user:
            user = User(email="demo@docflow.local")
            db.add(user)
            db.commit()
            db.refresh(user)

        file = File(
            user_id=user.id,
            original_name="demo-document.pdf",
            storage_path=str(sample),
            mime_type="application/pdf",
            file_size=sample.stat().st_size,
            page_count=2,
        )
        db.add(file)
        db.commit()
        db.refresh(file)

        job = Job(
            user_id=user.id,
            file_id=file.id,
            mode="general",
            output_format="markdown",
            status=JobStatus.completed,
            progress=100,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        for page_no in (1, 2):
            markdown = f"# Demo page {page_no}\n\nSeeded reviewed content for page {page_no}."
            db.add(
                PageResult(
                    job_id=job.id,
                    page_no=page_no,
                    raw_text=markdown,
                    raw_markdown=markdown,
                    reviewed_text=markdown,
                    reviewed_markdown=markdown,
                    confidence_summary={"overall": 0.98, "provider": "seed"},
                )
            )
        db.add(
            StructuredResult(
                job_id=job.id,
                template_type="general",
                raw_json={"title": "Demo document"},
                reviewed_json={"title": "Demo document"},
            )
        )
        db.commit()
        print(f"Seeded demo job: {job.id}")


if __name__ == "__main__":
    main()
