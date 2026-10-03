// The guest's workshop session, stored when an invite is accepted.
const STORAGE_KEY = "participant";

export function readParticipantSession() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveParticipantSession(session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}
