/**
 * Header - Chat header with assistant avatar + name
 *
 * During onboarding: shows "Kameleon" + chameleon avatar
 */

function Header({ maturityLevel, isOnboarding }) {
  const displayName = isOnboarding ? 'Kameleon' : 'Assistant'
  const avatarEmoji = '\uD83E\uDD8E'

  return (
    <header className="chat-header">
      <div className="chat-header__spacer" />

      <div className="chat-header__avatar-name">
        <div className="chat-header__avatar" role="img" aria-label={`Avatar de ${displayName}`}>
          {avatarEmoji}
        </div>
        <span className="chat-header__name">{displayName}</span>
      </div>

      <div className="chat-header__spacer" />
    </header>
  )
}

export default Header
