/**
 * Header - Chat header with assistant avatar + name
 *
 * - During onboarding (maturityLevel === 1): shows "Kameleon" + no burger menu
 * - After onboarding (maturityLevel >= 2): shows assistant name + burger icon
 * - Burger icon is visible but non-functional in Phase 2 (placeholder for Phase 3)
 */

function Header({ assistantName, assistantGender, maturityLevel, isOnboarding }) {
  // Determine display name
  const displayName = assistantName || (isOnboarding ? 'Kameleon' : 'Assistant')

  // Determine avatar emoji based on gender
  let avatarEmoji
  if (assistantGender === 'female') {
    avatarEmoji = '👩'
  } else if (assistantGender === 'male') {
    avatarEmoji = '👨'
  } else {
    // Onboarding — generic Kameleon placeholder
    avatarEmoji = '🦎'
  }

  const showBurger = !isOnboarding || maturityLevel >= 2

  return (
    <header className="chat-header">
      {/* Left side placeholder or nothing */}
      <div className="chat-header__spacer" />

      {/* Center: avatar + name */}
      <div className="chat-header__avatar-name">
        <div className="chat-header__avatar" role="img" aria-label={`Avatar de ${displayName}`}>
          {avatarEmoji}
        </div>
        <span className="chat-header__name">{displayName}</span>
      </div>

      {/* Right side: burger (appears after onboarding) or spacer */}
      {showBurger ? (
        <button
          className="chat-header__burger"
          aria-label="Menu"
          title="Menu (disponible bientôt)"
          onClick={() => {/* Phase 3 */}}
        >
          <span className="chat-header__burger-line" />
          <span className="chat-header__burger-line" />
          <span className="chat-header__burger-line" />
        </button>
      ) : (
        <div className="chat-header__spacer" />
      )}
    </header>
  )
}

export default Header
