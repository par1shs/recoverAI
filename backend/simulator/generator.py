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

class DatasetMetadata(BaseModel):
    regime: str
    seed: int
    num_records: int
    generator_version: str = "1.1"

class SimulationDataset(BaseModel):
    metadata: DatasetMetadata
    records: List[FailedPaymentRecord]

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
    
    # Stress condition: unknown failure type
    if is_stress and random.random() > 0.9:
        failure_type = "unknown_system_error_503"
    
    # Stress condition: extreme amounts
    amount = round(random.uniform(500, 10000) if not is_stress else random.uniform(10000, 50000), 2)
    if is_stress and random.random() > 0.9:
        amount = round(random.uniform(100000, 500000), 2)
        
    # Stress condition: repeated failures / limits
    retry_count = random.randint(0, 3) if not is_stress else random.randint(0, 10)
    customer_tenure_months = random.randint(1, 48)
    previous_successes = max(0, customer_tenure_months - random.randint(0, 5))
    
    # Stress condition: unusual customer histories
    if is_stress and random.random() > 0.8:
        previous_successes = 0
        customer_tenure_months = 48
        
    previous_failures = random.randint(0, 5) if not is_stress else random.randint(5, 20)
    days_since_last_success = random.randint(1, 30)
    subscription_value = amount
    
    customer_message = None
    # Stress condition: missing customer messages
    if not is_stress or random.random() > 0.3:
        if failure_type in CUSTOMER_MESSAGES and CUSTOMER_MESSAGES[failure_type]:
            customer_message = random.choice(CUSTOMER_MESSAGES[failure_type])
            
    # Stress condition: noisy customer messages or conflicting signals
    if is_stress and random.random() > 0.5:
        if random.random() > 0.5:
            customer_message = "Random completely irrelevant text about a broken shoe."
        else:
            # Conflicting signal: temporary failure but message says "I cancelled my card"
            customer_message = "I cancelled my card permanently, don't try again."
        
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
        ground_truth_outcome = "stopped"  # default safe fallback

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

def generate_dataset(num_records: int, regime: str, seed: int, is_stress: bool = False) -> SimulationDataset:
    random.seed(seed)
    records = [generate_record(is_stress) for _ in range(num_records)]
    metadata = DatasetMetadata(
        regime=regime,
        seed=seed,
        num_records=num_records
    )
    return SimulationDataset(metadata=metadata, records=records)

if __name__ == "__main__":
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Generate synthetic failed payment data.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for generation.")
    parser.add_argument("--size", type=int, default=400, help="Number of records per dataset regime.")
    args = parser.parse_args()
    
    dev_set = generate_dataset(args.size, regime="development", seed=args.seed)
    test_set = generate_dataset(args.size, regime="held-out test", seed=args.seed + 1)
    stress_set = generate_dataset(args.size, regime="stress", seed=args.seed + 2, is_stress=True)
    
    os.makedirs("data", exist_ok=True)
    
    with open("data/dev.json", "w") as f:
        json.dump(dev_set.model_dump(), f, indent=2)
        
    with open("data/test.json", "w") as f:
        json.dump(test_set.model_dump(), f, indent=2)
        
    with open("data/stress.json", "w") as f:
        json.dump(stress_set.model_dump(), f, indent=2)
        
    print(f"Generated synthetic dataset: {args.size} dev, {args.size} test, {args.size} stress with base seed {args.seed}.")
