"""Seed three realistic candidates (with resume PDFs and embeddings).

Run once:  GEMINI_API_KEY=... .venv/bin/python seed.py
Idempotent — re-running overwrites the same uids.
"""
import main  # noqa: F401  (boots the schema)
from main import DATA_DIR, embed, extract_skills, get_db, load_embeddings, save_embeddings

CANDIDATES = [
    {
        "uid": "govind_9876543210",
        "name": "Govind G",
        "age": 21,
        "gender": "male",
        "experience_years": 1.5,
        "contact_no": "9876543210",
        "work_preference": "Remote",
        "bio": """Govind G is a B.Tech student in Electrical and Computer Engineering at the College of
Engineering Trivandrum (CET), Thiruvananthapuram, Kerala. His professional portfolio focuses on software
development, artificial intelligence, machine learning, embedded systems, digital electronics, and
hardware-software integration. His technical interests include Rust, C, Python, React, ESP32 development,
and AI-enabled applications.

Govind is associated with student technical organizations at CET, including VeloCET, the institution's
rocketry club, as well as GlitchCET and FossCET. His project portfolio reflects an interest in building
practical engineering tools, open-source software, embedded applications, and systems that integrate
hardware with modern software technologies.

KhagaLink is an open-source desktop telemetry and ground-station application developed using Rust, React,
and Tauri. The software is intended for rocketry and embedded-system applications, with features for
serial telemetry monitoring, CSV data analysis, live GPS mapping, and three-dimensional rocket-orientation
visualization.

VocEdge is a privacy-focused smart-home assistant that combines embedded hardware with local artificial
intelligence, documented on an ESP32-S3 with wake-word detection, speech recognition, local language-model
integration, and a web dashboard. DhalAI is a conversational financial-accessibility project which secured
the top position in the Allianz Technology National-Level Tech Championship 2025.

Other listed projects include a four-bit computer built using 74-series digital logic ICs, an eight-bit
computer simulation in C, a Markdown editor with language-model-assisted classification, and an SD-1000
model-rocket payload project involving STM32 and ESP32 hardware, sensor integration, telemetry, GNSS, and
Kalman-filter-based estimation. Kolam is a game-jam project associated with Global Game Jam Kochi 2026.

Overall Govind's documented work spans systems programming, desktop software, embedded electronics,
telemetry, AI integration, digital logic, and open-source development.

Sources: https://govindg.me/ https://in.linkedin.com/in/iamgovindg
https://github.com/govindgcoder/KhagaLink""",
    },
    {
        "uid": "karthik_9876543211",
        "name": "Karthik M Raj",
        "age": 21,
        "gender": "male",
        "experience_years": 0.5,
        "contact_no": "9876543211",
        "work_preference": "Hybrid",
        "bio": """Karthik M Raj is a student associated with the College of Engineering Trivandrum (CET),
Thiruvananthapuram, Kerala, with an association to VeloCET, a student engineering organization connected
with rocketry and technical projects.

Karthik's documented activities include an association with VeloCET. He is also listed as an event contact
for Sensor Fusion 101, a workshop associated with DRISHTI '26 and VeloCET. The event description focuses on
introductory sensor-fusion techniques using an ESP32 or Arduino Nano and an MPU6050 inertial measurement
unit, listed for 18 September 2026 at CET. This evidences involvement in the public organization of an
embedded-systems and sensor-fusion-related event.

His public profile also contains an activity entry related to participation in RE-ACTION RUSH during
Athena '25, an event hosted at TKM College of Engineering, Kollam.

Based on currently documented information, Karthik's publicly visible technical and organizational
interests include student engineering activities, rocketry-related work, embedded hardware, sensor fusion,
ESP32 and Arduino prototyping, and events involving inertial measurement units.

Sources: https://in.linkedin.com/in/karthik-m-raj-361b06348
https://arinjo.in/events/sensor-fusion-101-drishti-26""",
    },
    {
        "uid": "vinayak_9876543212",
        "name": "Vinayak H",
        "age": 21,
        "gender": "male",
        "experience_years": 2.0,
        "contact_no": "9876543212",
        "work_preference": "On-site",
        "bio": """Vinayak H is a student at the College of Engineering Trivandrum (CET), Thiruvananthapuram,
Kerala, for the 2024-2028 period. His profile lists an association with IEEE Student Branch CET and
documents projects and achievements involving electronics, assistive technology, computer vision, hardware
prototyping, and student engineering competitions.

Smart Vision Glasses for the Blind, developed with Abhinav S, supports visually impaired users through
computer vision and audio-based feedback. The prototype uses a Raspberry Pi 4 and incorporates real-time
object detection, obstacle alerts, and voice feedback, with an earlier implementation that included
Google's Bard AI in the voice-feedback functionality.

The profile records first-place finishes for related smart-glasses presentations at Edubition 2K23 and the
Eureka 2K23 Science and Mathematics Expo, and a third-place listing in the Electrical and Computer
Engineering category of CET Project Expo 2026 for Smart Vision Glass for Blind. He secured first place in
GlideXtreme, a glider-making competition organized by the IEEE Aerospace and Electronic Systems Society
Student Branch Chapter at CET as part of TESLA '25 in March 2025.

He was selected as a Reliance Foundation Undergraduate Scholar in January 2025 and received recognition
from the India Book of Records in November 2024. Listed qualifications include an NPTEL Digital Circuits
certification issued in November 2025.

Vinayak's documented activities focus on assistive technology, computer vision, computer vision with
Raspberry Pi, electronics, digital logic, embedded hardware, prototyping, and engineering competitions.

Sources: https://in.linkedin.com/in/vinayak-h-07aa3a275""",
    },
    {
        "uid": "rahul_9876543213",
        "name": "Rahul Menon",
        "age": 27,
        "gender": "male",
        "experience_years": 4.5,
        "contact_no": "9876543213",
        "work_preference": "Remote",
        "bio": """Rahul Menon is a DevOps and cloud infrastructure engineer based in Bengaluru with four and a
half years of professional experience. He specializes in automating build, deployment, and platform
operations for high-traffic web services.

His daily work centres on AWS, Docker, and Kubernetes, running containerized workloads across multiple
availability zones. He writes Terraform modules to provision infrastructure as code, and builds CI/CD
pipelines that run automated tests and blue-green deployments on every merge to main.

Rahul is fluent in Linux systems administration, shell scripting, and Python automation. He monitors
production with Prometheus and Grafana, tunes autoscaling policies, and leads incident response. He has
reduced deployment lead time from hours to under ten minutes for a payments platform.

Previously he worked as a backend developer using Python and PostgreSQL, which gives him a strong grasp of
the application side of the systems he now operates.

Sources: https://in.linkedin.com/in/rahul-menon-devops""",
    },
    {
        "uid": "ananya_9876543214",
        "name": "Ananya Sharma",
        "age": 25,
        "gender": "female",
        "experience_years": 3.0,
        "contact_no": "9876543214",
        "work_preference": "Hybrid",
        "bio": """Ananya Sharma is a digital marketing specialist with three years of experience growing
organic and paid acquisition for direct-to-consumer brands. She is based in Pune.

Her core strengths are SEO, Google Ads campaign management, and content marketing strategy. She plans
keyword roadmaps, writes and optimizes long-form content, and runs technical SEO audits that lift organic
traffic. On the paid side she structures search and performance campaigns, manages budgets, and improves
return on ad spend through continuous A/B testing.

Ananya is comfortable working with analytics and data: she pulls numbers with SQL, builds funnel
dashboards, and reports on conversion rate, customer acquisition cost, and lifetime value. She has scaled a
brand's monthly organic sessions from twelve thousand to over one hundred thousand in under two years.

She also collaborates with design and engineering teams to improve landing page experience and
conversion.

Sources: https://in.linkedin.com/in/ananya-sharma-marketing""",
    },
    {
        "uid": "sneha_9876543215",
        "name": "Sneha Iyer",
        "age": 24,
        "gender": "female",
        "experience_years": 2.5,
        "contact_no": "9876543215",
        "work_preference": "On-site",
        "bio": """Sneha Iyer is a UI/UX designer based in Kochi with two and a half years of experience
designing web and mobile products end to end.

She runs user research to understand needs, sketches flows, and produces high-fidelity interactive
prototypes in Figma. Her process covers information architecture, wireframing, usability testing, and
building component-based design systems that engineers can implement directly.

Sneha works closely with frontend developers and has hands-on HTML and CSS skills, plus a working
knowledge of React, so she can prototype in code and hand off accessible, responsive designs. She is
particularly focused on accessibility and inclusive design.

Her portfolio includes a fintech onboarding redesign that cut drop-off by thirty percent and a
health-tracking app used by over fifty thousand people.

Sources: https://in.linkedin.com/in/sneha-iyer-ux""",
    },
]

FIELDS = ("uid", "name", "age", "gender", "experience_years", "contact_no",
          "work_preference", "skills", "resume_path")


def write_pdf(path, title, body):
    """Minimal single-page text PDF — enough for the 'View Resume PDF' button."""
    def esc(t):
        return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    lines = [title, ""] + [ln for ln in body.splitlines() if ln.strip()]
    content = "BT /F1 9 Tf 40 752 Td 12 TL\n"
    for i, line in enumerate(lines[:62]):
        text = esc(line[:105])
        content += f"({text}) Tj T*\n" if i else f"({text}) Tj T*\n"
    content += "ET"
    stream = content.encode("latin-1", "replace")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body_obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body_obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    path.write_bytes(bytes(out))


def seed():
    embs = load_embeddings()
    conn = get_db()
    for c in CANDIDATES:
        pdf = DATA_DIR / f"{c['uid']}.pdf"
        write_pdf(pdf, c["name"], c["bio"])
        skills = ", ".join(extract_skills(c["bio"]))
        conn.execute(
            f"INSERT OR REPLACE INTO candidates ({', '.join(FIELDS)}) "
            f"VALUES ({', '.join('?' * len(FIELDS))})",
            (c["uid"], c["name"], c["age"], c["gender"], c["experience_years"],
             c["contact_no"], c["work_preference"], skills, str(pdf)),
        )
        # Embed the raw biodata directly: search must rank on prose, not on a
        # PDF-parse round trip, and the vector is what search_vectors() caches.
        embs[c["uid"]] = embed(c["bio"])
        print(f"  {c['name']:16} skills={skills}")
    conn.commit()
    conn.close()
    save_embeddings()
    print(f"Seeded {len(CANDIDATES)} candidates, {len(embs)} embeddings cached.")


if __name__ == "__main__":
    seed()
