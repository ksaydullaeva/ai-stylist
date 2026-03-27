import React from 'react'

/** Static demo profile for UI preview — not persisted */
const DEMO_PROFILE = {
  name: 'Alex Morgan',
  phone: '+1 (555) 014-2297',
  birthDate: 'March 12, 1996',
  gender: 'Woman',
  sizes: {
    tops: 'M (US 8)',
    bottoms: 'W29 × L32',
    dress: 'US 8',
    shoes: 'EU 39 / US 8.5',
  },
}

function Row({ label, value }) {
  return (
    <div className="settings-row">
      <span className="settings-label">{label}</span>
      <span className="settings-value">{value}</span>
    </div>
  )
}

export default function SettingsPage() {
  const { name, phone, birthDate, gender, sizes } = DEMO_PROFILE

  return (
    <section className="settings-page">
      <p className="settings-demo-note">Demo profile for preview. Values are not saved or synced.</p>

      <div className="settings-card">
        <h2 className="settings-card-title">About you</h2>
        <div className="settings-dl">
          <Row label="Name" value={name} />
          <Row label="Phone" value={phone} />
          <Row label="Birth date" value={birthDate} />
          <Row label="Gender" value={gender} />
        </div>
      </div>

      <div className="settings-card">
        <h2 className="settings-card-title">Sizes</h2>
        <div className="settings-dl">
          <Row label="Tops" value={sizes.tops} />
          <Row label="Bottoms" value={sizes.bottoms} />
          <Row label="Dress" value={sizes.dress} />
          <Row label="Shoes" value={sizes.shoes} />
        </div>
      </div>
    </section>
  )
}
