PLAN_MAX_MAILBOXES = {
    "founder": 20,
    "starter": 1,
    "base": 5,
    "super-active": 15,
}


def max_mailboxes(plan: str) -> int:
    return PLAN_MAX_MAILBOXES.get(plan, 1)
