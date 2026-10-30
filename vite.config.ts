import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const deepSeekSystemPrompt = `你是 HerMotion 的女性身体状态陪伴助手。你的任务不是诊断、治疗或替用户做医学判断，而是理解她此刻的身体感受、需求、空间和是否愿意开启摄像头，为她从本地动作库中选择一段可以马上开始的短练习。

只返回 JSON，不要 Markdown，不要额外解释。JSON 结构必须是：
{
  "reply": "自然、具体、回应用户原话的中文说明，最多 500 字",
  "recommendation": {
    "domain": "yoga" 或 "pilates",
    "variant": "chair" 或 "regular",
    "title": "方案标题",
    "duration": 2、3 或 5,
    "exerciseIds": ["本地动作 ID"],
    "requiresCamera": true 或 false,
    "reason": "为什么适合此刻，最多 240 字"
  },
  "alternatives": []
}

必须遵守：
1. exerciseIds 只能使用请求中 exerciseCatalog 的本地动作库 ID，最多 5 个，不重复；同一方案只能全是椅子瑜伽或全是常规动作。
2. 用户在工位/小空间，或不愿开启摄像头时，只能推荐 chair 方案，requiresCamera 必须为 false。
3. 只有用户明确愿意开启摄像头且有完整活动空间时，才可以推荐 regular 方案。
4. reply 和 reason 必须回应用户的自然语言，不要只重复固定模板。
5. 不使用“诊断、治疗、处方、疾病、气血、体质”等医学结论，不对图像或舌苔下医学判断。
6. 如果用户描述疼痛、头晕、胸闷、胸痛、呼吸困难或出血增加，不自行推荐练习；但正常情况下这些内容已由前端拦截。`

function json(res: any, status: number, payload: unknown) {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(payload))
}

function deepSeekProxy(apiKey: string): Plugin {
  return {
    name: 'hermotion-deepseek-proxy',
    configureServer(server) {
      server.middlewares.use((req: any, res: any, next: () => void) => {
        if (req.url !== '/api/chat') {
          next()
          return
        }
        if (req.method !== 'POST') {
          res.statusCode = 405
          res.setHeader('Allow', 'POST')
          res.end('Method Not Allowed')
          return
        }
        if (!apiKey) {
          json(res, 503, { error: 'DeepSeek API is not configured.' })
          return
        }

        let raw = ''
        req.setEncoding('utf8')
        req.on('data', (chunk: string) => {
          raw += chunk
          if (raw.length > 1_000_000) req.destroy()
        })
        req.on('end', async () => {
          try {
            const input = JSON.parse(raw) as Record<string, unknown>
            const response = await fetch('https://api.deepseek.com/chat/completions', {
              method: 'POST',
              headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({
                model: 'deepseek-chat',
                temperature: 0.25,
                response_format: { type: 'json_object' },
                messages: [
                  { role: 'system', content: deepSeekSystemPrompt },
                  { role: 'user', content: JSON.stringify(input) },
                ],
              }),
            })
            const payload = await response.json() as { choices?: Array<{ message?: { content?: string } }>; error?: unknown }
            if (!response.ok) {
              json(res, response.status, { error: 'DeepSeek request failed.' })
              return
            }
            const content = payload.choices?.[0]?.message?.content
            if (typeof content !== 'string' || !content.trim()) {
              json(res, 502, { error: 'DeepSeek returned an empty response.' })
              return
            }
            let result: unknown
            try {
              result = JSON.parse(content)
            } catch {
              json(res, 502, { error: 'DeepSeek returned invalid JSON.' })
              return
            }
            json(res, 200, result)
          } catch {
            json(res, 502, { error: 'DeepSeek proxy request failed.' })
          }
        })
        req.on('error', () => {
          if (!res.writableEnded) json(res, 400, { error: 'Invalid request body.' })
        })
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  return {
    plugins: [react(), deepSeekProxy(env.DEEPSEEK_API_KEY)],
    server: {
      watch: { ignored: ['**/.runtime/**', '**/.venv-runtime/**', '**/output/**'] },
    },
  }
})
