/** User profile data returned by `GET /api/v1/users/me`. */
export interface User {
  id: string;
  email: string;
  displayName: string;
  gravatarEmail: string | null;
  role: string;
  status: string;
  createdAt: string;
}
