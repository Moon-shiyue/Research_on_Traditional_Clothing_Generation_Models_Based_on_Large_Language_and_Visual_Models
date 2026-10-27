<script setup>
import { ref, watch } from 'vue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  modelValue: Number, disabled: Boolean, precision: Number,
  controls: { type: Boolean, default: true }, size: String, controlsPosition: String,
})
const emit = defineEmits(['change'])
const display = value => Number.isFinite(value) && props.precision != null ? value.toFixed(props.precision) : value
const draft = ref(display(props.modelValue))
const dirty = ref(false)
let submitted

watch(() => props.modelValue, value => {
  draft.value = display(value)
  dirty.value = false
  submitted = undefined
})

// Keep typing local. Commit on change, blur or Enter; repeated events from the
// same edit must not start two pattern generations while the server responds.
function commit() {
  if (props.disabled || !dirty.value) return
  let value = draft.value === '' || draft.value == null ? NaN : Number(draft.value)
  if (!Number.isFinite(value)) {
    draft.value = display(props.modelValue)
    dirty.value = false
    return
  }
  if (props.precision != null) value = Number(value.toFixed(props.precision))
  draft.value = display(value)
  dirty.value = false
  if (value === Number(display(props.modelValue)) || value === submitted) return
  submitted = value
  emit('change', value)
}
</script>

<template>
  <input
    v-bind="$attrs"
    v-model="draft"
    type="number"
    class="el-input-number committed-number"
    :class="{ 'without-controls': !controls }"
    :disabled="disabled"
    :aria-valuenow="Number(draft)"
    @input="dirty = true"
    @change="commit"
    @blur="commit"
    @keydown.enter.prevent="commit"
  />
</template>

<style scoped>
.committed-number {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: var(--el-fill-color-blank, white);
  color: var(--el-text-color-regular, #606266);
  font: inherit;
  font-size: 12px;
}
.committed-number:focus { outline: 1px solid var(--el-color-primary); }
.committed-number:disabled { background: var(--el-disabled-bg-color, #f5f7fa); color: #a8abb2; cursor: not-allowed; }
.without-controls { appearance: textfield; }
.without-controls::-webkit-inner-spin-button { appearance: none; }
</style>
