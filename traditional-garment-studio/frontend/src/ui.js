import {
  ElAlert, ElAside, ElButton, ElConfigProvider, ElContainer, ElDialog,
  ElForm, ElFormItem, ElHeader, ElIcon, ElInput, ElMain, ElOption,
  ElPopover, ElProgress, ElRadioButton, ElRadioGroup, ElSelect, ElSlider,
  ElSwitch, ElTabPane, ElTabs, ElTag, ElTooltip, ElLoading, ElMessageBox,
} from 'element-plus'

export function registerUI(app) {
  // Some child exports have a no-op install method. Registering their names
  // explicitly keeps radio groups and tab panes available after tree shaking.
  for (const component of [
    ElAlert, ElAside, ElButton, ElConfigProvider, ElContainer, ElDialog,
    ElForm, ElFormItem, ElHeader, ElIcon, ElInput, ElMain, ElOption,
    ElPopover, ElProgress, ElRadioButton, ElRadioGroup, ElSelect, ElSlider,
    ElSwitch, ElTabPane, ElTabs, ElTag, ElTooltip,
  ]) app.component(component.name, component)
  app.use(ElLoading)
  app.use(ElMessageBox)
}
