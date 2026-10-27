<script setup>
defineProps({ apiMode: { type: String, default: 'mock' } })
</script>

<template>
  <el-header height="48px" class="app-header">
    <div class="brand">传统服饰智能制版系统</div>
    <div class="links">
      <el-tag v-if="apiMode === 'mock'" size="small" type="warning" effect="plain" class="mode-tag">
        Mock 模式
      </el-tag>
      <a href="https://style3d.github.io/design2garmentcode/" target="_blank" class="plain-link">项目主页</a>
      <a href="http://arxiv.org/abs/2412.08603" target="_blank" class="plain-link">arXiv</a>
      <a href="https://github.com/Style3D/design2garmentcode-impl" target="_blank" class="plain-link">GitHub</a>
    </div>
  </el-header>
</template>

<style scoped>
.app-header {
  background: var(--c-header-bg);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}
.brand {
  font-size: 18px;
  font-weight: 500;
}
.links {
  display: flex;
  align-items: center;
  gap: 14px;
}
.mode-tag {
  margin-right: 4px;
}
.plain-link {
  color: #fff;
  text-decoration: none;
  font-size: 14px;
}
.plain-link:hover {
  opacity: 0.8;
}
@media (max-width: 800px) {
  .app-header { padding: 0 10px; gap: 10px; }
  .brand { font-size: 14px; flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .links { gap: 8px; flex-shrink: 0; }
  .plain-link { font-size: 11px; }
}
</style>
