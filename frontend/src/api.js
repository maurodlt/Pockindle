const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export async function api(path, options = {}) {
  const response = await fetch(`${base}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`)
  }
  return response.json()
}
export const list = entity => api(`/${entity}/`)
export const get = (entity, id) => api(`/${entity}/${id}/`)
export const save = (entity, values, id) => api(`/${entity}/${id ? `${id}/` : ''}`, { method: id ? 'PUT' : 'POST', body: JSON.stringify(values) })
export const remove = (entity, id) => api(`/${entity}/${id}/`, { method: 'DELETE' })
