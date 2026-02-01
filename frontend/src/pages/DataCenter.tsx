import { useEffect, useState } from 'react'
import Modal from '../components/Modal'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import { AxiosResponse } from 'axios'
import DatePicker from '../components/DatePicker'

interface StockItem {
    symbol: string
    name: string
    market: string
}

export default function DataCenter() {
    const { pushToast } = useToast()
    const [stocks, setStocks] = useState<StockItem[]>([])
    const [loading, setLoading] = useState(false)
    const [page, setPage] = useState(1)
    const [total, setTotal] = useState(0)
    const [search, setSearch] = useState('')
    const [syncOpen, setSyncOpen] = useState(false)
    const [progressOpen, setProgressOpen] = useState(false)
    const [progress, setProgress] = useState<{ status: string, message: string, current: number, total: number }>({ status: 'idle', message: '', current: 0, total: 0 })
    const [dateRange, setDateRange] = useState({ start: '', end: '' })
    const pageSize = 18

    const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0

    // Progress polling
    useEffect(() => {
        let interval: any
        if (progressOpen) {
            interval = setInterval(() => {
                api.get('/data/sync/progress').then(res => {
                    setProgress(res.data)
                    if (res.data.status === 'finished' || res.data.status === 'error') {
                        // Delay closing to let user see 100%
                        if (res.data.status === 'finished') {
                            setTimeout(() => {
                                setProgressOpen(false)
                                pushToast('任务已完成', 'success')
                                fetchStocks()
                            }, 1000)
                        } else {
                            setProgressOpen(false)
                            pushToast(`任务出错: ${res.data.message}`, 'error')
                        }
                    }
                })
            }, 1000)
        }
        return () => clearInterval(interval)
    }, [progressOpen])

    const syncDaily = () => {
        if (!dateRange.start || !dateRange.end) {
            pushToast('请选择日期范围', 'error')
            return
        }
        setSyncOpen(false)
        setLoading(true)
        pushToast('行情同步任务已后台启动，请稍候...', 'info')

        api.post('/data/sync/daily', { start_date: dateRange.start, end_date: dateRange.end })
            .then((res: AxiosResponse<{ count: number }>) => {
                pushToast(`行情同步成功，更新 ${res.data.count} 条记录`, 'success')
                setPage(1)
                fetchStocks()
            })
            .catch(() => {
                pushToast('行情同步失败', 'error')
                setLoading(false)
            })
            .finally(() => {
                // Keep loading true for a bit or just rely on fetchStocks? 
                // Actually fetchStocks in .then will handle loading state effectively by chaining or separate call.
                // But if we failed, we must turn off loading.
                // Let's rely on .catch turning off loading. 
                // If success, we call fetchStocks which sets loading=true internally. 
                // But we need to ensure local loading is off if we don't fetchStocks?
                // Actually fetchStocks handles its own loading state.
                // So strictly speaking, we might not need separate setLoading(false) in finally if we chain correctly.
                // But let's be safe.
                if (loading) setLoading(false)
            })
    }

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1)
            fetchStocks()
        }, 500)
        return () => clearTimeout(timer)
    }, [search])

    useEffect(() => {
        fetchStocks()
    }, [page])

    const fetchStocks = () => {
        setLoading(true)
        api.get('/stocks/query', { params: { keyword: search, limit: pageSize, offset: (page - 1) * pageSize } })
            .then((res: AxiosResponse<{ total: number, items: StockItem[] }>) => {
                setStocks(res.data.items)
                setTotal(res.data.total)
            })
            .catch(() => pushToast('股票列表加载失败', 'error'))
            .finally(() => setLoading(false))
    }


    // ... sync functions (syncStockList, syncDaily) remain same but should reload stocks on success ...
    const syncStockList = () => {
        setLoading(true)
        api.post('/data/sync/stocks')
            .then((res: AxiosResponse<{ count: number }>) => {
                pushToast(`股票清单同步完成，共 ${res.data.count} 条`, 'success')
                setPage(1)
                fetchStocks()
            })
            .catch(() => pushToast('股票清单同步失败，请检查权限', 'error'))
            .finally(() => setLoading(false))
    }

    // ... syncDaily ...

    const totalPages = Math.ceil(total / pageSize)

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-semibold">数据中心</h2>
                    <p className="text-sm text-muted-foreground">多数据源同步与数据完整性管理</p>
                </div>
                <div className="flex gap-3">
                    <button
                        className="rounded-xl border border-border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                        onClick={() => setSyncOpen(true)}
                        disabled={loading}
                    >
                        同步行情
                    </button>
                    <button
                        className="rounded-xl bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        onClick={syncStockList}
                        disabled={loading}
                    >
                        {loading && (
                            <svg className="animate-spin h-3 w-3 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        )}
                        同步股票清单
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-5">
                <div className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 p-6 shadow-lg">
                    <div className="relative z-10">
                        <p className="text-sm font-medium text-white/80">数据覆盖</p>
                        <div className="mt-3 flex items-baseline gap-2">
                            <span className="text-4xl font-bold text-white">{total}</span>
                            <span className="text-sm font-medium text-white/70">只股票</span>
                        </div>
                        <p className="mt-3 text-xs text-white/60">全市场A股数据已纳入</p>
                    </div>
                    <div className="absolute -right-4 -bottom-4 opacity-20">
                        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-white">
                            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
                        </svg>
                    </div>
                </div>

                <div className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-400 p-6 shadow-lg">
                    <div className="relative z-10">
                        <p className="text-sm font-medium text-white/80">数据源状态</p>
                        <div className="mt-3 flex items-center gap-2">
                            <span className="flex h-2.5 w-2.5 rounded-full bg-white animate-pulse"></span>
                            <span className="text-2xl font-bold text-white">运行正常</span>
                        </div>
                        <p className="mt-3 text-xs text-white/60">多源并发 · 自动故障转移</p>
                    </div>
                    <div className="absolute -right-4 -bottom-4 opacity-20">
                        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-white">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                    </div>
                </div>

                <div className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-purple-500 to-pink-400 p-6 shadow-lg">
                    <div className="relative z-10">
                        <p className="text-sm font-medium text-white/80">更新模式</p>
                        <div className="mt-3">
                            <span className="text-xl font-bold text-white">自动 + 手动</span>
                        </div>
                        <p className="mt-3 text-xs text-white/60">每日15:35自动同步</p>
                    </div>
                    <div className="absolute -right-4 -bottom-4 opacity-20">
                        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-white">
                            <path d="M21 12a9 9 0 00-9-9 9.75 9.75 0 00-6.74 2.74L3 8" /><path d="M3 3v5h5" /><path d="M3 12a9 9 0 009 9 9.75 9.75 0 006.74-2.74L21 16" /><path d="M16 16h5v5" />
                        </svg>
                    </div>
                </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-lg font-semibold">当前股票清单</h3>
                    <div className="flex gap-4 items-center">
                        <input
                            placeholder="搜索股票代码或名称..."
                            className="w-64 rounded-lg border border-border px-3 py-1.5 text-sm"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                        <span className="text-xs text-muted-foreground">共 {total} 只</span>
                    </div>
                </div>
                {loading ? (
                    <Loading />
                ) : (
                    <>
                        <div className="grid grid-cols-3 gap-3 text-sm">
                            {stocks.map((item) => (
                                <div key={item.symbol} className="rounded-xl border border-border px-3 py-2 bg-white/50 hover:bg-white transition-colors">
                                    <div className="font-medium">{item.name}</div>
                                    <div className="text-xs text-muted-foreground">{item.symbol} · {item.market}</div>
                                </div>
                            ))}
                        </div>
                        <div className="flex items-center justify-between border-t border-border mt-4 pt-4">
                            <div className="text-xs text-muted-foreground">
                                第 {page} / {totalPages || 1} 页
                            </div>
                            <div className="flex gap-2">
                                <button
                                    disabled={page <= 1}
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    className="rounded-lg border border-border px-3 py-1 text-xs disabled:opacity-50 hover:bg-slate-100"
                                >
                                    上一页
                                </button>
                                <button
                                    disabled={page >= totalPages}
                                    onClick={() => setPage((p) => p + 1)}
                                    className="rounded-lg border border-border px-3 py-1 text-xs disabled:opacity-50 hover:bg-slate-100"
                                >
                                    下一页
                                </button>
                            </div>
                        </div>
                    </>
                )}
            </div>

            <Modal open={progressOpen} onClose={() => { }} title="任务执行中" footer={null}>
                <div className="space-y-4 py-4">
                    <div className="flex justify-between text-sm text-slate-600">
                        <span>{progress.message || '正在初始化任务...'}</span>
                        <span className="font-medium">{percent}%</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full bg-primary transition-all duration-300 ease-out" style={{ width: `${percent}%` }} />
                    </div>
                    <p className="text-xs text-muted-foreground text-center">请勿关闭窗口，正在后台处理数据...</p>
                </div>
            </Modal>

            <Modal
                open={syncOpen}
                title="行情数据同步"
                onClose={() => setSyncOpen(false)}
                footer={(
                    <div className="flex justify-end gap-3">
                        <button className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-slate-50 transition-colors" onClick={() => setSyncOpen(false)}>取消</button>
                        <button className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 transition-colors" onClick={syncDaily}>开始同步</button>
                    </div>
                )}
            >
                <div className="space-y-4">
                    <div>
                        <label className="text-xs text-muted-foreground">起始日期</label>
                        <div className="mt-2">
                            <DatePicker value={dateRange.start} onChange={(date) => setDateRange((prev) => ({ ...prev, start: date }))} placeholder="选择起始日期" />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs text-muted-foreground">结束日期</label>
                        <div className="mt-2">
                            <DatePicker value={dateRange.end} onChange={(date) => setDateRange((prev) => ({ ...prev, end: date }))} placeholder="选择结束日期" />
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        同步任务需要管理员权限，建议在交易日收盘后执行。
                        <a href="/logs" className="ml-2 text-primary underline underline-offset-2">查看同步日志</a>
                    </p>
                </div>
            </Modal>
        </div>
    )
}
