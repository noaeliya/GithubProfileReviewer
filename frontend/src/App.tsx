import { FormEvent, useState } from "react";
import type { ReviewResponse, RepoAssessment } from "./types";

// Colour-code the level badge so the summary is scannable at a glance.
function levelClass(level: string): string {
  const l = level.toLowerCase();
  if (l.includes("advanced")) return "badge badge-advanced";
  if (l.includes("intermediate")) return "badge badge-intermediate";
  if (l.includes("basic")) return "badge badge-basic";
  return "badge badge-unknown";
}

function RepoCard({ repo }: { repo: RepoAssessment }) {
  return (
    <article className="card">
      <header className="card-header">
        <a href={repo.url} target="_blank" rel="noreferrer" className="repo-name">
          {repo.repo}
        </a>
        <span className={levelClass(repo.level)}>{repo.level}</span>
      </header>

      <div className="meta">
        {repo.language && <span>🛠 {repo.language}</span>}
        <span>⭐ {repo.stars}</span>
        <span>📄 README: {repo.readme_clarity}</span>
      </div>

      {repo.description && <p className="description">{repo.description}</p>}
      <p className="assessment">{repo.assessment}</p>
    </article>
  );
}

export default function App() {
  const [username, setUsername] = useState("");
  const [data, setData] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;

    setLoading(true);
    setError(null);
    setData(null);

    try {
      const resp = await fetch(
        `/api/review?username=${encodeURIComponent(username.trim())}`
      );
      const body = await resp.json();
      if (!resp.ok) {
        throw new Error(body.detail || "Something went wrong");
      }
      setData(body as ReviewResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <h1>🔍 GitHub Profile Reviewer</h1>
      <p className="subtitle">
        Enter a GitHub username or profile URL. Each public repo's README is
        rated by Claude.
      </p>

      <form onSubmit={handleSubmit} className="search">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="e.g. torvalds or https://github.com/torvalds"
          aria-label="GitHub username"
        />
        <button type="submit" disabled={loading}>
          {loading ? "Reviewing…" : "Review"}
        </button>
      </form>

      {loading && <p className="status">Fetching repos and asking Claude… ⏳</p>}
      {error && <p className="status error">⚠️ {error}</p>}

      {data && (
        <section>
          <p className="summary">
            <strong>{data.username}</strong> has {data.repo_count} public repos.
            Showing {data.reviewed_count} most-recently-updated.
          </p>
          {data.results.length === 0 ? (
            <p className="status">No public repositories to review.</p>
          ) : (
            <div className="cards">
              {data.results.map((repo) => (
                <RepoCard key={repo.repo} repo={repo} />
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
