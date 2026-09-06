import os
import json
from flask import Flask, request, jsonify, send_from_directory
from firebase_admin import credentials, initialize_app, auth, firestore
import google.generativeai as genai
from flask_cors import CORS

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

cred_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
if cred_json:
    cred = credentials.Certificate(json.loads(cred_json))
    initialize_app(cred)
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

    # MODIFICATION 1: Strict brevity enforced in the prompt to prevent API timeouts
    prompt = f"""
    Act as an elite Market Intelligence Engine advising a 'Hack2skill Gen AI Academy APAC Edition' participant. 
    Contextualize "APAC" specifically as the Hack2skill cohort, startup network, and developer ecosystem—focusing on practical Google Cloud GenAI innovations—rather than geographic boundaries or cities.

    Business: {business_name}
    Industry: {industry}
    Audience: {audience}
    Budget: {budget}

    CRITICAL INSTRUCTION: You must be extremely concise to ensure fast API response times. Limit every single generated text field to 1 short sentence maximum. 

    Generate an exhaustive 5-stage go-to-market strategy:
    Stage 1: Local ID & Demographics (Audience profiling and ecosystem footprint).
    Stage 2: Market Trends & Demand Signals (Tech disruptions and demand whitespace).
    Stage 3: Competitor & Brand Audit (Direct/indirect matrix and value prop gaps).
    Stage 4: Strategic Brand Positioning (Core identity, positioning wedge, and messaging pillars).
    Stage 5: Turnkey Execution Roadmap (30-60-90 day GTM phasing, detailing Google Cloud GenAI tools and Hack2skill community activations).
    """

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                max_output_tokens=800, # MODIFICATION 2: Hard limit on output length to beat the Render timeout
                response_schema={
                    "type": "object",
                    "properties": {
                        "stage_1_local_id": {
                            "type": "object",
                            "properties": {
                                "demographics_and_culture": {"type": "string", "description": "Cultural nuances and localized buyer behaviors"},
                                "audience_segmentation": {"type": "string", "description": "Primary and secondary ICPs with pain points"},
                                "channel_suitability": {"type": "string", "description": "Digital and community gathering places"}
                            },
                            "required": ["demographics_and_culture", "audience_segmentation", "channel_suitability"]
                        },
                        "stage_2_market_trends": {
                            "type": "object",
                            "properties": {
                                "macro_micro_trends": {"type": "string", "description": "Fast-moving tech and industry trends"},
                                "demand_and_whitespace": {"type": "string", "description": "Unmet customer frustrations and high-demand segments"},
                                "pricing_dynamics": {"type": "string", "description": "Prevailing spending thresholds in the market"}
                            },
                            "required": ["macro_micro_trends", "demand_and_whitespace", "pricing_dynamics"]
                        },
                        "stage_3_competitor_audit": {
                            "type": "object",
                            "properties": {
                                "competitor_matrix": {"type": "string", "description": "Direct and indirect competitor breakdown"},
                                "value_prop_gap": {"type": "string", "description": "Where competitors fail and uncontested territory exists"}
                            },
                            "required": ["competitor_matrix", "value_prop_gap"]
                        },
                        "stage_4_brand_strategy": {
                            "type": "object",
                            "properties": {
                                "core_identity": {"type": "string", "description": "Mission, vision, and core values"},
                                "positioning_statement": {"type": "string", "description": "Exact wedge: Why you, why now, why this ecosystem"},
                                "messaging_pillars": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Targeted angles for awareness, consideration, and conversion"
                                }
                            },
                            "required": ["core_identity", "positioning_statement", "messaging_pillars"]
                        },
                        "stage_5_action_plan": {
                            "type": "object",
                            "properties": {
                                "days_1_to_30": {"type": "string", "description": "Foundation and setup actions"},
                                "days_31_to_60": {"type": "string", "description": "Market penetration and pilot campaigns"},
                                "days_61_to_90": {"type": "string", "description": "Scale, retention loops, and referral mechanisms"},
                                "gen_ai_tools_to_leverage": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Specific AI technologies to implement"
                                },
                                "community_activations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Hack2skill community, startup network, and APAC ecosystem leverage points"
                                }
                            },
                            "required": ["days_1_to_30", "days_31_to_60", "days_61_to_90", "gen_ai_tools_to_leverage", "community_activations"]
                        }
                    },
                    "required": [
                        "stage_1_local_id",
                        "stage_2_market_trends",
                        "stage_3_competitor_audit",
                        "stage_4_brand_strategy",
                        "stage_5_action_plan"
                    ]
                }
            )
        )
        plan = json.loads(response.text)
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
    
