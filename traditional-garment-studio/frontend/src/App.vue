<script setup>
import { onMounted, ref } from 'vue'
import { useChatStore } from './stores/chat'
import { useDesignStore } from './stores/design'
import { apiMode } from './api'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import AppHeader from './components/AppHeader.vue'
import ChatPanel from './components/ChatPanel.vue'
import ParamPanel from './components/ParamPanel.vue'
import BodyPanel from './components/BodyPanel.vue'
import PatternView from './components/PatternView.vue'

const chat = useChatStore()
const design = useDesignStore()

const activeTab = ref('parse')
const viewTab = ref('2d')

onMounted(() => {
  chat.loadVocab()
  design.loadAll()
})
</script>

<template>
  <el-config-provider :locale="zhCn">
  <el-container class="app-shell">
    <AppHeader :api-mode="apiMode" />

    <div v-if="design.loadError" class="service-error">
      <el-alert :title="design.loadError" type="warning" show-icon :closable="false" />
      <el-button size="small" :disabled="chat.task.running || design.patternUpdating" @click="design.loadAll()">刷新状态</el-button>
    </div>

    <el-container class="main-row">
      <!-- 左侧：参数/聊天面板 -->
      <el-aside width="440px" class="left-panel">
        <el-tabs v-model="activeTab" class="left-tabs">
          <el-tab-pane name="parse">
            <template #label><el-icon><ChatDotRound /></el-icon>&nbsp;设计解析</template>
            <ChatPanel />
          </el-tab-pane>
          <el-tab-pane name="design">
            <template #label><el-icon><ShoppingBag /></el-icon>&nbsp;设计参数</template>
            <ParamPanel />
          </el-tab-pane>
          <el-tab-pane name="body">
            <template #label><el-icon><User /></el-icon>&nbsp;人体尺寸</template>
            <BodyPanel />
          </el-tab-pane>
        </el-tabs>
      </el-aside>

      <!-- 右侧：版型视图 -->
      <el-main class="right-panel">
        <el-tabs v-model="viewTab" class="right-tabs">
          <el-tab-pane label="裁片版型" name="2d">
            <PatternView />
          </el-tab-pane>
          <el-tab-pane name="3d" disabled>
            <template #label>3D 预览（二期）</template>
          </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>
  </el-container>
  </el-config-provider>
</template>
