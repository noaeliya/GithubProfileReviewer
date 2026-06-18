// Mirrors the backend Pydantic models (app/models.py).

export interface RepoAssessment {
  repo: string;
  description: string | null;
  language: string | null;
  stars: number;
  url: string;
  has_readme: boolean;
  level: string;
  readme_clarity: string;
  assessment: string;
}

export interface ReviewResponse {
  username: string;
  profile_url: string;
  repo_count: number;
  reviewed_count: number;
  results: RepoAssessment[];
}
