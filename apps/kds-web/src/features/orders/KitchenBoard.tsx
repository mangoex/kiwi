import React, { useCallback, useEffect, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Badge, Button, Card } from '@restaurantos/ui';
import { AlertTriangle, ChefHat, CheckCircle, Clock, Play, RefreshCcw } from 'lucide-react';

type TaskStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED';

interface KdsTask {
  id: string;
  order_id: string;
  folio: string;
  product_name: string;
  quantity: number;
  station: string;
  status: TaskStatus;
  created_at: string;
}

interface KdsSession {
  permissions: string[];
  active_branch: { id: string; name: string } | null;
}

type ViewState = 'loading' | 'ready' | 'denied' | 'error';

const columns: Array<{
  status: TaskStatus;
  title: string;
  empty: string;
  icon: React.ReactNode;
  tone: string;
}> = [
  {
    status: 'PENDING',
    title: 'Pendiente',
    empty: 'No hay tareas esperando.',
    icon: <Clock size={20} />,
    tone: 'pending',
  },
  {
    status: 'IN_PROGRESS',
    title: 'Preparando',
    empty: 'No hay tareas en preparación.',
    icon: <ChefHat size={20} />,
    tone: 'progress',
  },
  {
    status: 'COMPLETED',
    title: 'Listo',
    empty: 'Todavía no hay tareas terminadas.',
    icon: <CheckCircle size={20} />,
    tone: 'ready',
  },
];

const elapsedLabel = (createdAt: string) => {
  const timestamp = Date.parse(createdAt);
  if (!Number.isFinite(timestamp)) return 'Hora no disponible';
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
  return minutes < 1 ? 'Ahora' : `Hace ${minutes} min`;
};

const KitchenBoard = () => {
  const [tasks, setTasks] = useState<KdsTask[]>([]);
  const [branch, setBranch] = useState<KdsSession['active_branch']>(null);
  const [viewState, setViewState] = useState<ViewState>('loading');
  const [error, setError] = useState('');
  const [transitioning, setTransitioning] = useState<string | null>(null);

  const loadTasks = useCallback(async (branchId: string) => {
    try {
      const result = await fetchApi<KdsTask[]>(
        `/kds/tasks?branch_id=${encodeURIComponent(branchId)}`,
      );
      setTasks(Array.isArray(result) ? result : []);
      setViewState('ready');
      setError('');
    } catch (reason) {
      setViewState(reason instanceof ApiError && reason.status === 403 ? 'denied' : 'error');
      setError(reason instanceof ApiError ? reason.message : 'No fue posible consultar cocina.');
    }
  }, []);

  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      try {
        const session = await fetchApi<KdsSession>('/auth/session');
        if (!active) return;
        if (!session.permissions.includes('kds.tasks.operate')) {
          setViewState('denied');
          setError('Tu usuario no tiene permiso para operar KDS.');
          return;
        }
        if (!session.active_branch) {
          setViewState('error');
          setError('Selecciona una sucursal autorizada antes de abrir KDS.');
          return;
        }
        setBranch(session.active_branch);
        await loadTasks(session.active_branch.id);
      } catch (reason) {
        if (!active) return;
        setViewState(reason instanceof ApiError && reason.status === 403 ? 'denied' : 'error');
        setError(
          reason instanceof ApiError && reason.status === 401
            ? 'Inicia sesión para abrir KDS.'
            : reason instanceof ApiError
              ? reason.message
              : 'No fue posible validar la sesión.',
        );
      }
    };
    void bootstrap();
    return () => { active = false; };
  }, [loadTasks]);

  useEffect(() => {
    if (!branch) return undefined;
    const interval = window.setInterval(() => { void loadTasks(branch.id); }, 5_000);
    return () => window.clearInterval(interval);
  }, [branch, loadTasks]);

  const transitionTask = async (task: KdsTask) => {
    const nextStatus = task.status === 'PENDING' ? 'IN_PROGRESS' : 'COMPLETED';
    setTransitioning(task.id);
    setError('');
    try {
      await fetchApi(`/kds/tasks/${encodeURIComponent(task.id)}/transition`, {
        method: 'POST',
        body: JSON.stringify({ status: nextStatus, branch_id: branch?.id }),
      });
      if (branch) await loadTasks(branch.id);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'No fue posible actualizar la tarea.');
    } finally {
      setTransitioning(null);
    }
  };

  return (
    <main className="kds-layout" aria-busy={viewState === 'loading'}>
      <header className="kds-header">
        <div className="kds-brand"><ChefHat size={28} /><strong>Sistema KDS</strong></div>
        <div className="kds-header-context">
          <Badge variant="info">{branch?.name || 'Sin sucursal'}</Badge>
          {branch && (
            <Button size="sm" variant="secondary" onClick={() => void loadTasks(branch.id)}>
              <RefreshCcw size={15} /> Actualizar
            </Button>
          )}
        </div>
      </header>

      {viewState !== 'ready' ? (
        <section className="kds-state" role={viewState === 'error' ? 'alert' : 'status'}>
          {viewState === 'loading' ? <RefreshCcw className="kds-spin" size={34} /> : <AlertTriangle size={34} />}
          <strong>{viewState === 'loading' ? 'Cargando tareas…' : error}</strong>
        </section>
      ) : (
        <>
          {error && <p className="kds-inline-error" role="alert">{error}</p>}
          <section className="kds-board" aria-label="Tareas de producción">
            {columns.map((column) => {
              const columnTasks = tasks.filter((task) => task.status === column.status);
              return (
                <div key={column.status} className={`kds-column ${column.tone}`}>
                  <div className="kds-column-header">
                    <div className="kds-column-title">{column.icon}{column.title}</div>
                    <div className="kds-column-count">{columnTasks.length}</div>
                  </div>
                  {columnTasks.length === 0 && <p className="kds-empty">{column.empty}</p>}
                  {columnTasks.map((task) => (
                    <Card key={task.id} className="kds-order-card">
                      <div className="kds-order-content">
                        <div className="kds-order-header">
                          <div><span>Pedido</span><strong>{task.folio}</strong></div>
                          <span className="kds-order-time">{elapsedLabel(task.created_at)}</span>
                        </div>
                        <div className="kds-order-item">
                          <strong>{task.quantity} × {task.product_name}</strong>
                          <span>{task.station}</span>
                        </div>
                        {task.status !== 'COMPLETED' && (
                          <div className="kds-order-footer">
                            <Button
                              size="sm"
                              variant="primary"
                              disabled={transitioning === task.id}
                              onClick={() => void transitionTask(task)}
                            >
                              {task.status === 'PENDING' ? <Play size={15} /> : <CheckCircle size={15} />}
                              {transitioning === task.id
                                ? 'Guardando…'
                                : task.status === 'PENDING'
                                  ? 'Iniciar'
                                  : 'Completar'}
                            </Button>
                          </div>
                        )}
                      </div>
                    </Card>
                  ))}
                </div>
              );
            })}
          </section>
        </>
      )}
    </main>
  );
};

export default KitchenBoard;
