import os
import json
from flask import Flask, request, jsonify, send_from_directory
from firebase_admin import credentials, initialize_app, auth, firestore
import google.generativeai as genai
from flask_cors import CORS

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

import json as _json
_cred_json = __import__("os").environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
if _cred_json:
    _cred = credentials.Certificate(_json.loads(_cred_json))
    initialize_app(_cred)
else:
    initialize_app()
db = firestore.client()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")


def verify_token(req):
    header = req.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    id_token = header.split("Bearer ")[1]
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception:
        return None


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/generate-plan", methods=["POST"])
def generate_plan():
    uid = verify_token(request)
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    business_name = data.get("business_name", "")
    industry = data.get("industry", "")
    audience = data.get("audience", "")
    budget = data.get("budget", "")

    prompt = f"""
Act as an elite AI Marketing Mentor advising the 'Hack2skill Gen AI Academy APAC Edition' cohort. 
Do NOT generate generic, random business advice. You must provide a hyper-tailored, real-world strategy that directly leverages Gen AI tools, developer communities, and the specific context of the Hack2skill APAC cohort.

Business Details provided by the participant:
Name: {business_name}
Industry: {industry}
Target Audience: {audience}
Monthly budget: {budget}

Make sure the ad copy, budget, and action steps mention real AI tools, tech community platforms (e.g., GitHub, Discord, Dev.to), and reference the Hack2skill ecosystem.

Return the result STRICTLY as a valid JSON object with no markdown formatting and exactly these keys:
- "ad_copy": array of 3 compelling, tech-forward ad copy variations tailored to or leveraging the Hack2skill APAC Gen AI cohort.
- "budget_split": object mapping channel names (e.g., "Gen AI APIs & Tools", "Hack2skill Community Events", "Dev Outreach (Discord/GitHub)") to percentage numbers that sum to 100.
- "trend_summary": a short paragraph (2-3 sentences) summarizing real-world Gen AI adoption and tech trends relevant to this hackathon cohort.
- "recommended_actions": array of 3 short actionable next steps mentioning real Gen AI tools or Hack2skill community actions.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        plan = json.loads(text.strip())
    except Exception as e:
        return jsonify({"error": f"Generation failed: {str(e)}"}), 500

    doc_ref = db.collection("users").document(uid).collection("plans").document()
    doc_ref.set({
        "business_name": business_name,
        "industry": industry,
        "audience": audience,
        "budget": budget,
        "plan": plan,
        "created_at": firestore.SERVER_TIMESTAMP,
    })

    return jsonify({"plan": plan, "id": doc_ref.id})


@app.route("/api/history", methods=["GET"])
def history():
    uid = verify_token(request)
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    docs = (
        db.collection("users").document(uid).collection("plans")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(10)
        .stream()
    )
    results = []
    for d in docs:
        item = d.to_dict()
        item["id"] = d.id
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        results.append(item)
    return jsonify({"history": results})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
            
