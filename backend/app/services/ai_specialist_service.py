from app.repositories import ParticipantRepository, RunRepository


class AISpecialistService:
    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo

    def get_ai_specialist(self, run_id: int, owner_user_id: int):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')

        specialist = self.participant_repo.find_ai_by_run(run_id)
        if specialist is None:
            raise ValueError('AI specialist not found')
        return specialist

    def upsert_ai_specialist(
        self,
        run_id: int,
        owner_user_id: int,
        display_name: str,
        ai_specialty: str,
    ):
        # The Run row lock serializes specialist configuration for this Run.
        run = self.run_repo.get_for_update(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')

        specialist = self.participant_repo.find_ai_by_run(run_id)
        if specialist is None:
            return self.participant_repo.create_ai_specialist(
                run_id=run_id,
                display_name=display_name,
                ai_specialty=ai_specialty,
            )

        return self.participant_repo.update_ai_specialist(
            specialist,
            display_name=display_name,
            ai_specialty=ai_specialty,
        )
