<template>
    <el-card>
      <template #header><h3>AI 智能对话</h3></template>
      <div class="chat-container">
        <div class="chat-messages" ref="msgBox">
          <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
            <div class="msg-content">{{ msg.content }}</div>
          </div>
          <div v-if="streaming" class="msg assistant"><div class="msg-content streaming">{{ streamText }}<span class="cursor">|</span></div></div>
        </div>
        <div class="chat-input">
          <el-input v-model="input" placeholder="输入消息..." @keyup.enter="send" :disabled="streaming">
            <template #append>
              <el-button @click="send" :disabled="streaming">发送</el-button>
            </template>
          </el-input>
        </div>
      </div>
    </el-card>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import axios from 'axios'

const input = ref('')
const messages = ref([])
const streaming = ref(false)
const streamText = ref('')
const msgBox = ref(null)

async function send() {
  if (!input.value.trim() || streaming.value) return
  const userMsg = input.value
  messages.value.push({ role: 'user', content: userMsg })
  input.value = ''
  streaming.value = true
  streamText.value = ''

  try {
    const resp = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: messages.value.map(m => ({ role: m.role, content: m.content })),
        stream: true,
      }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let done = false
    while (!done) {
      const { value, done: d } = await reader.read()
      done = d
      if (value) {
        const text = decoder.decode(value)
        for (const line of text.split('\n')) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            try { streamText.value += JSON.parse(data).choices[0]?.delta?.content || '' } catch (_) {}
          }
        }
      }
    }
  } catch (e) { streamText.value = 'Error: ' + e.message }
  messages.value.push({ role: 'assistant', content: streamText.value })
  streaming.value = false
  streamText.value = ''
  await nextTick()
  msgBox.value?.scrollTo(0, msgBox.value.scrollHeight)
}
</script>

<style scoped>
.chat-container { display: flex; flex-direction: column; }
.chat-messages { height: 60vh; overflow-y: auto; padding: 10px; background: #f5f7fa; border-radius: 8px; margin-bottom: 12px; }
.msg { margin: 8px 0; display: flex; }
.msg.user { justify-content: flex-end; }
.msg.user .msg-content { background: #409eff; color: #fff; }
.msg.assistant .msg-content { background: #fff; border: 1px solid #e4e7ed; }
.msg-content { padding: 10px 16px; border-radius: 12px; max-width: 70%; white-space: pre-wrap; }
.streaming .msg-content { background: #fff; border: 1px solid #e4e7ed; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
