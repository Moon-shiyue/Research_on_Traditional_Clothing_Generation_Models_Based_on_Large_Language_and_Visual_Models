import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { registerUI } from './ui.js'
import 'element-plus/dist/index.css'
import { ChatDotRound, ShoppingBag, User, Document, Loading, PictureFilled, Promotion, Download } from '@element-plus/icons-vue'
import App from './App.vue'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
registerUI(app)
for (const [key, component] of Object.entries({ ChatDotRound, ShoppingBag, User, Document, Loading, PictureFilled, Promotion, Download })) {
  app.component(key, component)
}
app.mount('#app')
