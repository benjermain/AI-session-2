"""
Generate synthetic long transcripts for evaluation. Produces variations where a critical fact appears early.
"""
from typing import List, Dict
import time


def generate_40_turn_with_allergy(patient_id: str = 'p1', allergy_text: str = 'penicillin reaction - hives') -> List[Dict]:
    transcript = []
    # Turn 1-3: initial conversation, include allergy at turn 3
    transcript.append({'type':'turn','speaker':'owner','text':'Hello, my dog is acting odd','created_at':time.time()})
    transcript.append({'type':'turn','speaker':'owner','text':'He has been vomiting','created_at':time.time()+1})
    transcript.append({'type':'turn','speaker':'owner','text':f'He had a {allergy_text} when he was a puppy','created_at':time.time()+2,'patient_id':patient_id})
    # 4-37: many tool outputs and turns
    for i in range(4,38):
        if i % 3 == 0:
            transcript.append({'type':'tool','tool_name':'fetch_prescriptions','text':'[large prescription JSON ...]', 'created_at':time.time()+i})
        else:
            transcript.append({'type':'turn','speaker':'agent','text':f'Follow-up question {i}', 'created_at':time.time()+i})
    # 38-40: vet asks final
    transcript.append({'type':'turn','speaker':'vet','text':'Any allergy concerns before we prescribe?', 'created_at':time.time()+38})
    transcript.append({'type':'turn','speaker':'agent','text':'', 'created_at':time.time()+39})
    transcript.append({'type':'turn','speaker':'vet','text':'Please confirm allergy status.', 'created_at':time.time()+40})
    return transcript
