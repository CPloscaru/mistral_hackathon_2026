/**
 * useSubdomain - Detects persona from hostname subdomain
 *
 * Maps:
 *   sophie.localhost -> creator persona (onboarding, no pre-set assistant name)
 *   lea.localhost    -> freelance persona (Lisa, female)
 *   marc.localhost   -> merchant persona (Andy, male)
 *   unknown          -> defaults to sophie (creator)
 */

const PERSONA_MAP = {
  sophie: {
    persona: 'creator',
    assistantName: null,
    assistantGender: null,
    isOnboarding: true,
    avatarEmoji: null,
  },
  lea: {
    persona: 'freelance',
    assistantName: 'Lisa',
    assistantGender: 'female',
    isOnboarding: false,
    avatarEmoji: '👩',
  },
  marc: {
    persona: 'merchant',
    assistantName: 'Andy',
    assistantGender: 'male',
    isOnboarding: false,
    avatarEmoji: '👨',
  },
}

const DEFAULT_PERSONA = PERSONA_MAP.sophie

function parseSubdomain() {
  const hostname = window.location.hostname
  // hostname: "sophie.localhost" -> subdomain: "sophie"
  const parts = hostname.split('.')
  if (parts.length >= 2) {
    const subdomain = parts[0].toLowerCase()
    return PERSONA_MAP[subdomain] || DEFAULT_PERSONA
  }
  return DEFAULT_PERSONA
}

export function useSubdomain() {
  // Static — hostname doesn't change during session
  return parseSubdomain()
}
