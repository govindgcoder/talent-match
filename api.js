const API_BASE = "http://localhost:8000";

// --- Candidate API ---
export async function uploadCandidate({ name, age, gender, experience_years, contact_no, resume_file }) {
  const form = new FormData();
  form.append("name", name);
  form.append("age", age);
  form.append("gender", gender);
  form.append("experience_years", experience_years);
  form.append("contact_no", contact_no);
  form.append("resume_file", resume_file);

  const res = await fetch(`${API_BASE}/api/candidates/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export function getResumeUrl(uid) {
  return `${API_BASE}/api/candidates/${encodeURIComponent(uid)}/resume`;
}

// --- Recruiter API ---
export async function registerCompany(companyData) {
  const res = await fetch(`${API_BASE}/api/company/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(companyData),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Company registration failed" }));
    throw new Error(err.detail || "Company registration failed");
  }
  return res.json();
}

export async function getCompanyList() {
  const res = await fetch(`${API_BASE}/api/company/list`);
  if (!res.ok) throw new Error("Failed to fetch companies");
  return res.json();
}

export async function getCompanyApplicants(companyId) {
  const res = await fetch(`${API_BASE}/api/company/${encodeURIComponent(companyId)}/applicants`);
  if (!res.ok) throw new Error("Failed to fetch applicants");
  return res.json();
}

export async function searchCandidates({ query, min_experience, gender }) {
  const params = new URLSearchParams();
  if (query) params.set("query", query);
  if (min_experience !== undefined && min_experience !== null) params.set("min_experience", min_experience);
  if (gender) params.set("gender", gender);

  const res = await fetch(`${API_BASE}/api/candidates/search?${params}`);
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}
