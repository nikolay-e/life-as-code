from agent.agent import HealthAgent


def generate_daily_briefing(user_id: int) -> str:
    agent = HealthAgent()
    return str(agent.daily_briefing(user_id))


def generate_weekly_report(user_id: int) -> str:
    agent = HealthAgent()
    return str(agent.weekly_report(user_id))


def explain_anomaly(user_id: int, anomaly: dict) -> str:
    agent = HealthAgent()
    return str(agent.explain_anomaly(user_id, anomaly))
