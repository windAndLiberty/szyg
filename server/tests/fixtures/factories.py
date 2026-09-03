"""Test data factories — avoid repetitive data construction across tests."""

def make_user(username="testuser", password="test123", role="admin"):
    return {"username": username, "password": password, "role": role}

def make_conversation(title="测试对话", messages=None):
    return {
        "title": title,
        "messages": messages or [],
        "model": "doubao-seed-2-0-pro-260215",
    }

def make_staff_task(agent_id="content", title="测试任务"):
    return {"agent_id": agent_id, "title": title, "status": "pending"}

def make_content(title="测试内容", content_type="video", platform="douyin"):
    return {"title": title, "content_type": content_type, "platform": platform}

def make_hermes_message(content="你好，请用中文回复"):
    return {"role": "user", "content": content}
