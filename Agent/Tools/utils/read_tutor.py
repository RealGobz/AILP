import os
from azure.cosmos import CosmosClient

def describe_tutor(user_id, book_id, cosmos_client: CosmosClient ):
    db_name = os.getenv("COSMOS_DATABASE_NAME")
    cont_name = os.getenv("COSMOS_USER_GRADINGS_CONTAINER_NAME")

    database = cosmos_client.get_database_client(db_name)
    container = database.get_container_client(cont_name)

    try:
        item = container.read_item(item=str(user_id), partition_key=str(user_id))
    except Exception:
        return f"No tutor info found for this user under the book id: {book_id}"

    tutors = item.get("tutors", {})

    if not tutors or book_id not in tutors:
        return f"No tutor info found for this user under the book id: {book_id}"

    tutor = tutors.get(book_id, {})
    if not tutor:
        return f"No tutor info found for this user under the book id: {book_id}"

    tutor_name = list(tutor.keys())[0]
    tutor_data = tutor[tutor_name].get("data", {})
    
    q_types = tutor_data.get("question_types", [])
    question_types = "\n".join(q_types) if isinstance(q_types, list) else str(q_types)
    
    e_tricks = tutor_data.get("exam_tricks", [])
    exam_tricks = "\n".join(e_tricks) if isinstance(e_tricks, list) else str(e_tricks)
    
    how_tricky = tutor_data.get("how_tricky", "Not specified")

    return f"Tutor name: {tutor_name}\nQuestion types: {question_types}\nExam tricks: {exam_tricks}\nHow tricky: {how_tricky}"
