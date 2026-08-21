import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import StatusPill from '@/components/StatusPill.vue'

describe('StatusPill', () => {
  it('renders an accessible state label and state class', () => {
    const wrapper = mount(StatusPill, {
      props: { status: 'ok', label: '运行正常' },
    })

    expect(wrapper.text()).toContain('运行正常')
    expect(wrapper.classes()).toContain('status-pill--ok')
  })

  it('renders disabled dependencies without treating them as errors', () => {
    const wrapper = mount(StatusPill, {
      props: { status: 'disabled', label: '本地未启用' },
    })

    expect(wrapper.text()).toContain('本地未启用')
    expect(wrapper.classes()).toContain('status-pill--disabled')
  })
})
