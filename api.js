const API_BASE = "http://localhost:8000";

// test
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

export async function searchCandidates({ query, min_experience, gender, limit = 10 }) {
  const params = new URLSearchParams();
  if (query) params.set("query", query);
  if (min_experience !== undefined && min_experience !== null) params.set("min_experience", min_experience);
  if (gender) params.set("gender", gender);
  params.set("limit", limit);

  const res = await fetch(`${API_BASE}/api/candidates/search?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Search failed" }));
    throw new Error(err.detail || "Search failed");
  }

  return res.json();
}
