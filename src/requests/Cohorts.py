import typing
import httpx
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(20.0)


async def create_cohort(token: str, org_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/create"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text or f"Server error ({res.status_code})"}
    except Exception as e:
        print(f"create_cohort error: {e}")
        return {"error": str(e)}


async def get_cohorts(token: str, org_id: str) -> list:
    url = f"{api_url}/organisations/{org_id}/cohorts/"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return []
    except Exception as e:
        print(f"get_cohorts error: {e}")
        return []


async def get_cohort_details(token: str, org_id: str, cohort_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text or f"Server error ({res.status_code})"}
    except Exception as e:
        print(f"get_cohort_details error: {e}")
        return {"error": str(e)}


async def update_cohort(token: str, org_id: str, cohort_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def delete_cohort(token: str, org_id: str, cohort_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def add_cohort_courses(token: str, org_id: str, cohort_id: str, course_ids: list) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/courses"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json={"course_ids": course_ids})
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def remove_cohort_course(token: str, org_id: str, cohort_id: str, course_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/courses/{course_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def add_cohort_members(token: str, org_id: str, cohort_id: str, user_ids: list) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/members"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json={"user_ids": user_ids})
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def remove_cohort_member(token: str, org_id: str, cohort_id: str, user_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/members/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


# ── Exams ────────────────────────────────────────────────────────────────

async def create_cohort_exam(token: str, org_id: str, cohort_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text or f"Server error ({res.status_code})"}
    except Exception as e:
        return {"error": str(e)}


async def get_cohort_exam(token: str, org_id: str, cohort_id: str, exam_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def update_cohort_exam(token: str, org_id: str, cohort_id: str, exam_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def delete_cohort_exam(token: str, org_id: str, cohort_id: str, exam_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def add_exam_question(token: str, org_id: str, cohort_id: str, exam_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/questions"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def update_exam_question(token: str, org_id: str, cohort_id: str, exam_id: str, q_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/questions/{q_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def delete_exam_question(token: str, org_id: str, cohort_id: str, exam_id: str, q_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/questions/{q_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def upload_exam_questions_file(token: str, org_id: str, cohort_id: str, exam_id: str, file_bytes: bytes, filename: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/upload-questions"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_bytes, "application/octet-stream")}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), verify=ssl_context) as client:
            res = await client.post(url, headers=headers, files=files)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text or f"Upload failed ({res.status_code})"}
    except Exception as e:
        return {"error": str(e)}


async def get_exam_question_template_csv(token: str, org_id: str, cohort_id: str) -> str:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/template"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200 and res.text.strip():
                return res.text
    except Exception:
        pass
    
    # Standalone robust fallback
    return (
        "Scenario (Optional),Question,Option A,Option B,Option C,Option D,Correct Answer,Explanation,Points\n"
        "\"A 45-year-old patient presents to the clinic with sudden onset severe retrosternal chest pain radiating to the left jaw. Blood pressure is 85/50 mmHg, heart rate is 112 bpm, and ECG reveals ST-elevation in leads II, III, and aVF.\",Which coronary artery is most likely occluded based on the clinical presentation and ECG findings?,Right Coronary Artery (RCA),Left Anterior Descending (LAD),Left Circumflex (LCx),Left Main Coronary Artery,A,\"ST-elevation in leads II, III, and aVF indicates an inferior wall myocardial infarction, typically supplied by the RCA.\",2.0\n"
        ",What is the primary time complexity of binary search on a sorted array of length N?,O(log N),O(N),O(1),O(N log N),A,Binary search repeatedly divides the search interval in half.,1.0\n"
        "\"A financial analyst is evaluating two mutually exclusive projects with cost of capital 10%. Project Alpha NPV is $45k and IRR is 18%. Project Beta NPV is $52k and IRR is 14%.\",Which project should the firm select and why?,Project Beta because it yields the higher Net Present Value (NPV),Project Alpha because it has a superior Internal Rate of Return (IRR),Both projects simultaneously,Neither project,A,NPV is the preferred metric for mutually exclusive projects as it maximizes total value.,1.5\n"
    )


# ── Candidate Flow ───────────────────────────────────────────────────────

async def start_cohort_exam(token: str, org_id: str, cohort_id: str, exam_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/take"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text or f"Server error ({res.status_code})"}
    except Exception as e:
        return {"error": str(e)}


async def submit_cohort_exam(token: str, org_id: str, cohort_id: str, exam_id: str, payload: dict) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/submit"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                return {"error": res.json().get("detail", res.text)}
            except Exception:
                return {"error": res.text or f"Submission error ({res.status_code})"}
    except Exception as e:
        return {"error": str(e)}


# ── Gradebook & Results ──────────────────────────────────────────────────

async def get_exam_gradebook(token: str, org_id: str, cohort_id: str, exam_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/results"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"error": res.text}
    except Exception as e:
        return {"error": str(e)}


async def export_exam_gradebook_csv(token: str, org_id: str, cohort_id: str, exam_id: str) -> str:
    url = f"{api_url}/organisations/{org_id}/cohorts/{cohort_id}/exams/{exam_id}/export"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.text
            return ""
    except Exception as e:
        return ""


# ── Learner Flow ─────────────────────────────────────────────────────────

async def get_learner_cohorts(token: str) -> dict:
    url = f"{api_url}/organisations/learner/my-cohorts"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"cohorts": [], "active_urgent_exams": []}
    except Exception as e:
        print(f"get_learner_cohorts error: {e}")
        return {"cohorts": [], "active_urgent_exams": []}
