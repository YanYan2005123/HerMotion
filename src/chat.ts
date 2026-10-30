import { DOMAINS, getPracticeRecommendations, type Exercise, type PracticeRecommendation, type RecommendationContext } from './exercises'

export type CareAnalysis = {
  source: 'complexion' | 'tongue'
  label: string
  reliable: boolean
  advice: string[]
}

export type ChatNeed = 'relax' | 'clear' | 'open' | 'create'
export type ChatScene = 'desk' | 'open'
export type ChatMessage = { role: 'assistant' | 'user'; content: string }

export type ChatRecommendationResult = {
  reply: string
  recommendation: PracticeRecommendation
  alternatives: PracticeRecommendation[]
  source: 'ai' | 'local'
  blocked?: boolean
}

export type CareSession = {
  analysis: CareAnalysis
  need: ChatNeed
  scene: ChatScene
  duration: number
  cameraConsent: boolean
  messages: ChatMessage[]
  safetyFlags: string[]
}

export type RecommendationInput = {
  analysis: CareAnalysis
  need: ChatNeed
  scene: ChatScene
  duration: number
  cameraConsent: boolean
  messages: ChatMessage[]
}

const needLabels: Record<ChatNeed, string> = {
  relax: '放松一下',
  clear: '清醒一点',
  open: '打开身体',
  create: '进入创造状态',
}

const sceneLabels: Record<ChatScene, string> = {
  desk: '工位 / 小空间',
  open: '有完整活动空间',
}

const allowedDurations = new Set([2, 3, 5])
const safetyPattern = /疼痛|痛感|剧痛|刺痛|头晕|眩晕|胸闷|胸痛|呼吸困难|喘不上气|出血增加|明显不适/g
const negationPattern = /(?:没有|无|未|不|没|并无|并未|目前没有|现在没有|已经没有)(?:明显|任何|出现|感到|感觉到)?\s*$/

function getUserText(messages: ChatMessage[]): string {
  return messages.filter(message => message.role === 'user').map(message => message.content).join(' ')
}

function getSafetyFlags(messages: ChatMessage[]): string[] {
  const text = getUserText(messages)
  const flags: string[] = []
  safetyPattern.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = safetyPattern.exec(text)) !== null) {
    const before = text.slice(Math.max(0, match.index - 12), match.index)
    if (!negationPattern.test(before)) flags.push('user_reported_discomfort')
  }
  return [...new Set(flags)]
}

function buildCareSession(input: RecommendationInput): CareSession {
  return {
    analysis: input.analysis,
    need: input.need,
    scene: input.scene,
    duration: input.duration,
    cameraConsent: input.cameraConsent,
    messages: input.messages,
    safetyFlags: getSafetyFlags(input.messages),
  }
}

function getExercise(domain: 'yoga' | 'pilates', id: string): Exercise | undefined {
  return DOMAINS[domain].exercises.find(exercise => exercise.id === id)
}

function isMedicalClaim(value: string): boolean {
  return /处方|药物|用药|治疗|确诊|疾病|病症|气血|体质/.test(value)
}

function normalizeRecommendation(value: unknown, context: RecommendationContext): PracticeRecommendation | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Partial<PracticeRecommendation>
  if ((item.domain !== 'yoga' && item.domain !== 'pilates') || typeof item.title !== 'string' || !item.title.trim() || typeof item.reason !== 'string' || !item.reason.trim() || typeof item.duration !== 'number' || !allowedDurations.has(item.duration) || !Array.isArray(item.exerciseIds) || item.exerciseIds.length === 0 || item.exerciseIds.length > 5) return null

  const domain = item.domain
  const exerciseIds = [...new Set(item.exerciseIds.filter((id): id is string => typeof id === 'string' && Boolean(id.trim())))]
  if (exerciseIds.length !== item.exerciseIds.length) return null
  const exercises = exerciseIds.map(id => getExercise(domain, id))
  if (exercises.some(exercise => !exercise)) return null

  const resolved = exercises as Exercise[]
  const isChair = resolved.every(exercise => exercise.variant === 'chair' && exercise.requiresCamera === false)
  const isRegular = resolved.every(exercise => exercise.variant !== 'chair')
  if (!isChair && !isRegular) return null
  if (context.scene === 'desk' && !isChair) return null
  if (context.cameraConsent === false && !isChair) return null

  const variant = isChair ? 'chair' : 'regular'
  const requiresCamera = !isChair
  if (item.variant && item.variant !== variant) return null
  if (typeof item.requiresCamera === 'boolean' && item.requiresCamera !== requiresCamera) return null

  return {
    domain,
    variant,
    title: item.title.trim().slice(0, 80),
    duration: item.duration,
    exerciseIds,
    requiresCamera,
    reason: item.reason.trim().slice(0, 240),
  }
}

function buildLocalResult(input: RecommendationInput, blocked = false): ChatRecommendationResult {
  const context: RecommendationContext = { scene: input.scene, need: input.need, duration: input.duration, cameraConsent: input.cameraConsent }
  const recommendations = getPracticeRecommendations(context)
  const recommendation = recommendations[0]
  const imageNote = input.analysis.reliable ? `我参考了当前画面的“${input.analysis.label}”观感，但它不能替代对身体状态的判断。` : '这次画面不够稳定，我不会根据它做强判断。'
  const reply = blocked
    ? '你提到了一些需要先停下来的不适。先不要开始运动；如果不适持续、加重，或伴随明显呼吸/胸部症状，请及时寻求专业帮助。'
    : `${imageNote}结合你现在想${needLabels[input.need]}，${recommendation.reason}`
  return { reply, recommendation, alternatives: recommendations.slice(1), source: 'local', blocked }
}

export async function requestRecommendation(input: RecommendationInput): Promise<ChatRecommendationResult> {
  const session = buildCareSession(input)
  if (session.safetyFlags.length > 0) return buildLocalResult(input, true)

  const endpoint = (import.meta.env.VITE_AI_CHAT_API as string | undefined) || '/api/chat'
  if (endpoint) {
    try {
      const exerciseCatalog = {
        yoga: DOMAINS.yoga.exercises.map(exercise => ({ id: exercise.id, name: exercise.name, variant: exercise.variant ?? 'regular', scene: exercise.scene ?? 'open', requiresCamera: exercise.requiresCamera ?? exercise.variant !== 'chair' })),
        pilates: DOMAINS.pilates.exercises.map(exercise => ({ id: exercise.id, name: exercise.name, variant: exercise.variant ?? 'regular', scene: exercise.scene ?? 'open', requiresCamera: exercise.requiresCamera ?? exercise.variant !== 'chair' })),
      }
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...input, session, needLabel: needLabels[input.need], sceneLabel: sceneLabels[input.scene], exerciseCatalog }),
      })
      if (response.ok) {
        const payload = await response.json() as Partial<ChatRecommendationResult>
        const recommendation = normalizeRecommendation(payload.recommendation, session)
        const alternatives = Array.isArray(payload.alternatives)
          ? payload.alternatives.map(item => normalizeRecommendation(item, session)).filter((item): item is PracticeRecommendation => item !== null)
          : []
        if (typeof payload.reply === 'string' && payload.reply.trim() && !isMedicalClaim(payload.reply) && recommendation) {
          return { reply: payload.reply.trim().slice(0, 500), recommendation, alternatives, source: 'ai' }
        }
      }
    } catch {
      // Local fallback keeps the practice flow usable when the optional AI service is offline.
    }
  }

  return buildLocalResult(input)
}
