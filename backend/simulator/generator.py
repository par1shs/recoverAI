import uuid
import random
import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional

class FailedPaymentRecord(BaseModel):
    payment_id: str
    customer_id: str
    subscription_id: str
    amount: float
    failure_type: str
    retry_count: int
    customer_tenure_months: int
    previous_successes: int
    previous_failures: int
    days_since_last_success: int
    subscription_value: float
    customer_message: Optional[str] = None
    support_note: Optional[str] = None
    ground_truth_outcome: str

FAILURE_TYPES = [
    "temporary_bank_failure",
    "insufficient_funds",
    "expired_card",
    "mandate_failure",
    "permanent_decline"
]

CUSTOMER_MESSAGES = {
    "insufficient_funds": [
        "I get paid tomorrow, please don't cancel my subscription.",
        "Can you wait a few days?",
        "Sorry, waiting for my salary."
    ],
    "expired_card": [
        "Oh, I got a new card recently.",
        "How do I update my payment details?"
    ],
    "temporary_bank_failure": [
        "My bank app was down yesterday.",
        "Is there an issue with your payment gateway?"
    ],
    "permanent_decline": [
        "I blocked this merchant.",
        "Cancel my account."
    ]
}

def generate_record(is_stress: bool = False) -> FailedPaymentRecord:
    failure_type = random.choice(FAILURE_TYPES)
    
    amount = round(random.uniform(500, 10000) if not is_stress else random.uniform(10000, 50000), 2)
    retry_count = random.randint(0, 3) if not is_stress else random.randint(0, 10)
    customer_tenure_months = random.randint(1, 48)
    previous_successes = max(0, customer_tenure_months - random.randint(0, 5))
    previous_failures = random.randint(0, 5) if not is_stress else random.randint(5, 20)
    days_since_last_success = random.randint(1, 30)
    subscription_value = amount
    
    customer_message = None
    if random.random() > 0.5:
        if failure_type in CUSTOMER_MESSAGES and CUSTOMER_MESSAGES[failure_type]:
            customer_message = random.choice(CUSTOMER_MESSAGES[failure_type])
            
    # Add noise for stress set
    if is_stress and random.random() > 0.5:
        customer_message = "Random completely irrelevant text about something else."
        
    support_note = "Checked account, everything seems fine on our end." if random.random() > 0.8 else None
    
    # Ground truth outcome (simplified heuristic for what *should* eventually happen)
    if failure_type == "permanent_decline":
        ground_truth_outcome = "stopped"
    elif failure_type == "expired_card":
        ground_truth_outcome = "payment_link_sent"
    elif failure_type == "insufficient_funds":
        ground_truth_outcome = "recovered_after_delay"
    elif failure_type == "temporary_bank_failure":
        ground_truth_outcome = "recovered_on_retry"
    else:
        ground_truth_outcome = "recovered_after_delay"

    return FailedPaymentRecord(
        payment_id=f"pay_{uuid.uuid4().hex[:8]}",
        customer_id=f"cust_{uuid.uuid4().hex[:8]}",
        subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        amount=amount,
        failure_type=failure_type,
        retry_count=retry_count,
        customer_tenure_months=customer_tenure_months,
        previous_successes=previous_successes,
        previous_failures=previous_failures,
        days_since_last_success=days_since_last_success,
        subscription_value=subscription_value,
        customer_message=customer_message,
        support_note=support_note,
        ground_truth_outcome=ground_truth_outcome
    )

def generate_dataset(num_records: int, is_stress: bool = False) -> List[FailedPaymentRecord]:
    return [generate_record(is_stress) for _ in range(num_records)]

if __name__ == "__main__":
    # Generate splits
    dev_set = generate_dataset(200)
    test_set = generate_dataset(100)
    stress_set = generate_dataset(100, is_stress=True)
    
    import os
    os.makedirs("data", exist_ok=True)
    
    with open("data/dev.json", "w") as f:
        json.dump([r.model_dump() for r in dev_set], f, indent=2)
        
    with open("data/test.json", "w") as f:
        json.dump([r.model_dump() for r in test_set], f, indent=2)
        
    with open("data/stress.json", "w") as f:
        json.dump([r.model_dump() for r in stress_set], f, indent=2)
        
    print("Generated synthetic dataset: 200 dev, 100 test, 100 stress.")
