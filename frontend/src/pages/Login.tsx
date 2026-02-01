import { ChangeEvent, useState } from 'react'
import { z } from 'zod'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import { AxiosResponse } from 'axios'
import { useNavigate } from 'react-router-dom'

interface LoginForm {
    username: string
    password: string
}

const schema = z.object({
    username: z.string().min(2),
    password: z.string().min(6),
})

export default function Login() {
    const { pushToast } = useToast()
    const navigate = useNavigate()
    const [form, setForm] = useState<LoginForm>({ username: '', password: '' })

    const submit = () => {
        const parsed = schema.safeParse(form)
        if (!parsed.success) {
            pushToast('请输入正确的账号与密码', 'error')
            return
        }
        api.post('/auth/login', form)
            .then((res: AxiosResponse<{ token: string }>) => {
                localStorage.setItem('momentum_token', res.data.token)
                pushToast('登录成功', 'success')
                window.dispatchEvent(new Event('momentum-auth'))
                navigate('/', { replace: true })
            })
            .catch(() => pushToast('登录失败，请检查账号密码', 'error'))
    }

    return (
        <div className="flex h-screen items-center justify-center bg-background text-foreground">
            <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-sm">
                <h2 className="text-xl font-semibold">系统登录</h2>
                <p className="mt-2 text-sm text-muted-foreground">使用管理员或分析师账号进入系统</p>
                <div className="mt-6 space-y-4">
                    <div>
                        <label className="text-xs text-muted-foreground">账号</label>
                        <input className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm" value={form.username} onChange={(e: ChangeEvent<HTMLInputElement>) => setForm((prev: LoginForm) => ({ ...prev, username: e.target.value }))} />
                    </div>
                    <div>
                        <label className="text-xs text-muted-foreground">密码</label>
                        <input type="password" className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm" value={form.password} onChange={(e: ChangeEvent<HTMLInputElement>) => setForm((prev: LoginForm) => ({ ...prev, password: e.target.value }))} />
                    </div>
                    <button className="w-full rounded-xl bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90" onClick={submit}>登录</button>
                </div>
                <div className="mt-4 text-xs text-muted-foreground">默认账号：admin / 123456</div>
            </div>
        </div>
    )
}
