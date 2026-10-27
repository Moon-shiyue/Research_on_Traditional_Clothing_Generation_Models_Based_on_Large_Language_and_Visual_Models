// Normalize in the browser before the server's 8 MB / 20 MP upload checks.
// The original selected file stays on the device; only a bounded copy is sent.
export async function prepareImageUpload(file) {
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    await new Promise((resolve, reject) => {
      image.onload = resolve
      image.onerror = () => reject(new Error('无法读取这张图片，请选择有效的图片文件。'))
      image.src = url
    })
    const width = image.naturalWidth
    const height = image.naturalHeight
    if (!width || !height) throw new Error('图片尺寸无效，请重新选择。')
    if (Math.max(width, height) <= 1600 && file.size <= 7 * 1024 * 1024 &&
        ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return file
    const ratio = Math.min(1, 1600 / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width * ratio))
    canvas.height = Math.max(1, Math.round(height * ratio))
    const context = canvas.getContext('2d')
    if (!context) throw new Error('浏览器无法处理图片，请换一张较小的图片。')
    context.fillStyle = '#fff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .9))
    if (!blob) throw new Error('图片压缩未完成，请重新选择。')
    return new File([blob], 'reference.jpg', { type: 'image/jpeg' })
  } finally {
    URL.revokeObjectURL(url)
  }
}
