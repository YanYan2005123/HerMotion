import { useState } from 'react'
import { ArrowRight, ChevronLeft, MessageCircle, Send, Sparkles } from 'lucide-react'
import { requestRecommendation, type CareAnalysis, type ChatMessage, type ChatNeed, type ChatScene } from './chat'
import type { PracticeRecommendation } from './exercises'

type Props = {
  analysis: CareAnalysis
  onBack: () => void
  onChoose: (recommendation: PracticeRecommendation) => void
}

const needOptions: Array<{ value: ChatNeed; label: string }> = [
  { value: 'relax', label: '放松一下' },
  { value: 'clear', label: '清醒一点' },
  { value: 'open', label: '打开身体' },
  { value: 'create', label: '进入创造状态' },
]

const sceneOptions: Array<{ value: ChatScene; label: string }> = [
  { value: 'desk', label: '工位 / 小空间' },
  { value: 'open', label: '有完整活动空间' },
]

export default function ChatView({ analysis, onBack, onChoose }: Props) {
  const [need, setNeed] = useState<ChatNeed>('create')
  const [scene, setScene] = useState<ChatScene>('desk')
  const [cameraConsent, setCameraConsent] = useState(false)
  const [custom, setCustom] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: analysis.reliable ? `我看到了当前画面的“${analysis.label}”观感。它只是图像中的可见特征，我们再结合你此刻的感受，选一段合适的练习。` : '这次画面不够稳定，我不会替你下结论。你可以告诉我此刻更想要什么，再选择一段练习。' },
  ])
  const [result, setResult] = useState<Awaited<ReturnType<typeof requestRecommendation>> | null>(null)
  const [loading, setLoading] = useState(false)

  async function generate() {
    if (loading) return
    const userMessage = custom.trim() || `我想${needOptions.find(item => item.value === need)?.label}，现在在${sceneOptions.find(item => item.value === scene)?.label}。`
    const nextMessages = [...messages, { role: 'user' as const, content: userMessage }]
    setMessages(nextMessages)
    setCustom('')
    setLoading(true)
    const recommendation = await requestRecommendation({ analysis, need, scene, duration: scene === 'desk' ? 3 : 5, cameraConsent, messages: nextMessages })
    setResult(recommendation)
    setMessages(current => [...current, { role: 'assistant', content: recommendation.reply }])
    setLoading(false)
  }

  return <main className="chatWorkspace relative z-10 flex min-h-0 flex-1 flex-col px-6 pb-6 pt-5 md:px-10">
    <div className="workspaceHead chatHead"><div><span>HER MOTION / AI COMPANION</span><h1>和 AI 聊聊今天的状态</h1><p>先听见自己的需要，再选择一段适合当下的练习。</p></div><button className="backLink" onClick={onBack}><ChevronLeft className="h-4 w-4"/>返回识别结果</button></div>
    <section className="chatGrid">
      <aside className="liquidGlass analysisSnapshot"><div className="panelLabel"><span>01 · 图像参考</span><b>{analysis.source === 'tongue' ? 'TONGUE' : 'COMPLEXION'}</b></div><div className="snapshotMark"><Sparkles className="h-5 w-5"/><strong>{analysis.label}</strong></div><p>只描述当前画面中的可见特征，不代表医学诊断、气血或体质判断。</p><div className="snapshotAdvice">{analysis.advice.slice(0, 2).map(item => <span key={item}>{item}</span>)}</div></aside>
      <section className="liquidGlass chatPanel"><div className="panelLabel"><span>02 · AI CHAT</span><b>PRIVATE CONTEXT</b></div><div className="messageList">{messages.map((message, index) => <div className={`chatMessage ${message.role}`} key={`${message.role}-${index}`}><span>{message.role === 'assistant' ? <Sparkles className="h-3.5 w-3.5"/> : 'YOU'}</span><p>{message.content}</p></div>)}{loading && <div className="chatMessage assistant"><span><Sparkles className="h-3.5 w-3.5"/></span><p>正在根据你的选择整理一段练习…</p></div>}</div><div className="choiceGroup"><small>你现在更想</small><div className="choiceRow">{needOptions.map(option => <button key={option.value} className={need === option.value ? 'selected' : ''} onClick={() => setNeed(option.value)}>{option.label}</button>)}</div></div><div className="choiceGroup"><small>你所在的空间</small><div className="choiceRow">{sceneOptions.map(option => <button key={option.value} className={scene === option.value ? 'selected' : ''} onClick={() => setScene(option.value)}>{option.label}</button>)}</div></div><label className="cameraChoice"><input type="checkbox" checked={cameraConsent} onChange={event => setCameraConsent(event.target.checked)}/><span>如果练习需要，我愿意开启本次视觉陪伴</span></label><div className="chatComposer"><input value={custom} onChange={event => setCustom(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void generate() }} placeholder="也可以补充一句此刻的感受"/><button className="iconButton" title="发送并生成练习" onClick={() => void generate()} disabled={loading}><Send className="h-4 w-4"/></button></div><button className="btn-cut startBtn chatStart" onClick={() => void generate()} disabled={loading}><span>{loading ? '正在整理…' : '生成我的练习'}</span><ArrowRight className="h-4 w-4"/></button></section>
      <aside className="liquidGlass recommendationPanel"><div className="panelLabel"><span>03 · 推荐去处</span><b>{result?.source === 'ai' ? 'AI' : 'LOCAL FALLBACK'}</b></div>{result ? <>{result.blocked ? <><div className="recommendationBadge"><MessageCircle className="h-4 w-4"/><span>先暂停一下</span></div><h2>暂不开始练习</h2><p>{result.reply}</p></> : <><div className="recommendationBadge"><MessageCircle className="h-4 w-4"/><span>为你准备好了</span></div><h2>{result.recommendation.title}</h2><div className="recommendationMeta"><span>{result.recommendation.duration} 分钟</span><span>{result.recommendation.variant === 'chair' ? '椅子瑜伽' : result.recommendation.domain === 'pilates' ? '普拉提' : '瑜伽'}</span><span>{result.recommendation.requiresCamera ? '可开启视觉陪伴' : '无需摄像头'}</span></div><p>{result.recommendation.reason}</p><button className="btn-cut startBtn" onClick={() => onChoose(result.recommendation)}><span>进入这段练习</span><ArrowRight className="h-4 w-4"/></button>{result.alternatives[0] && <button className="alternativeButton" onClick={() => onChoose(result.alternatives[0])}>换一个方案 <ArrowRight className="h-3.5 w-3.5"/></button>}</>}</> : <div className="recommendationEmpty"><Sparkles className="h-7 w-7"/><b>你的练习会在这里出现</b><p>先告诉 AI 你此刻想要怎样的支持。</p></div>}</aside>
    </section>
  </main>
}
