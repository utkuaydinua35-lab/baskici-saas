// WebAuthn (geçiş anahtarı / passkey) yardımcıları.
// Sunucu base64url alanlarla options gönderir; tarayıcı ArrayBuffer ister.
import { api } from './api'

function b64uToBuf(b64u) {
  const b64 = b64u.replace(/-/g, '+').replace(/_/g, '/')
  const pad = b64.length % 4 ? '='.repeat(4 - (b64.length % 4)) : ''
  const bin = atob(b64 + pad)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes.buffer
}

function bufToB64u(buf) {
  const bytes = new Uint8Array(buf)
  let bin = ''
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function passkeySupported() {
  return !!(window.PublicKeyCredential && navigator.credentials && navigator.credentials.create)
}

async function doCreate(options) {
  const pk = { ...options }
  pk.challenge = b64uToBuf(pk.challenge)
  pk.user = { ...pk.user, id: b64uToBuf(pk.user.id) }
  if (pk.excludeCredentials) pk.excludeCredentials = pk.excludeCredentials.map(c => ({ ...c, id: b64uToBuf(c.id) }))
  const cred = await navigator.credentials.create({ publicKey: pk })
  const r = cred.response
  return {
    id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || undefined,
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
    response: {
      clientDataJSON: bufToB64u(r.clientDataJSON),
      attestationObject: bufToB64u(r.attestationObject),
      transports: r.getTransports ? r.getTransports() : undefined,
    },
  }
}

async function doGet(options) {
  const pk = { ...options }
  pk.challenge = b64uToBuf(pk.challenge)
  if (pk.allowCredentials) pk.allowCredentials = pk.allowCredentials.map(c => ({ ...c, id: b64uToBuf(c.id) }))
  const cred = await navigator.credentials.get({ publicKey: pk })
  const r = cred.response
  return {
    id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || undefined,
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
    response: {
      clientDataJSON: bufToB64u(r.clientDataJSON),
      authenticatorData: bufToB64u(r.authenticatorData),
      signature: bufToB64u(r.signature),
      userHandle: r.userHandle ? bufToB64u(r.userHandle) : undefined,
    },
  }
}

// Yeni passkey kaydet (giriş yapmışken). Döner: {ok, passkey}
export async function registerPasskey(name) {
  const { options, state } = await api.post('/api/auth/passkey/register/begin', {})
  const credential = await doCreate(options)
  return api.post('/api/auth/passkey/register/finish', { state, credential, name })
}

// Passkey ile giriş. Döner: {access_token, ...}
export async function loginPasskey() {
  const { options, state } = await api.post('/api/auth/passkey/login/begin', {})
  const credential = await doGet(options)
  return api.post('/api/auth/passkey/login/finish', { state, credential })
}
