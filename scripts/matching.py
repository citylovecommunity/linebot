from sqlalchemy.orm import Session
from shared.scoring import calculate_match_score
from shared.database.models import UserMatchScore


def run_grading_pipeline(session: Session, new_user_json: dict, target_user_json: dict):

    # 1. Calculate Score
    total_score, breakdown_data = calculate_match_score(
        new_user_json, target_user_json)

    # 2. Prepare DB Record
    match_record = UserMatchScore(
        # Assuming this is your ID mapping
        source_user_id=new_user_json["LINE ID"],
        target_user_id=target_user_json["LINE ID"],
        score=total_score,
        # Stores: {"age": 10, "hobbies": "+6 (Skiing, Art)"}
        breakdown=breakdown_data,
        logic_version="v1.0"      # Important for future updates
    )

    # 3. Upsert (Merge) - Updates if exists, Inserts if new
    session.merge(match_record)
    session.commit()


# --- Example Output Check ---
if __name__ == "__main__":
    # Test with the same user against themselves just to see logic flow
    score, details = calculate_match_score(sample_json, sample_json)
    print(f"Total Score: {score}")
    print(f"Details: {details}")
