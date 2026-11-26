import { ErrorState, LoadingBlock } from '../components/States'
import { useMethods } from '../data/hooks'
import { formatDate } from '../lib/format'
import { usePageMeta } from '../lib/usePageMeta'

type Baseline = { precision: number; recall: number; f1: number }

function baselineRows(value: unknown): [string, Baseline][] {
  if (!value || typeof value !== 'object') return []
  return Object.entries(value as Record<string, unknown>).flatMap(([name, row]) => {
    if (row && typeof row === 'object' && 'precision' in row && 'recall' in row && 'f1' in row) {
      return [[name, row as Baseline]]
    }
    return []
  })
}

export function MethodsPage() {
  usePageMeta({
    title: 'Methods - WikiPulse',
    description:
      'How WikiPulse detects spikes, scores events, and evaluates its classifier, with limitations.',
  })
  const methods = useMethods()
  if (methods.status === 'loading') return <LoadingBlock lines={8} />
  if (methods.status === 'error') {
    return <ErrorState message={methods.error} retry={methods.retry} />
  }
  const data = methods.data
  const baselines = baselineRows(data.classifier?.baselines)
  const ruleBaseline = baselines.find(([name]) => name === 'A_rule')?.[1]
  const classifierWeaker =
    data.classifier !== null &&
    ruleBaseline !== undefined &&
    data.classifier.event_f1 < ruleBaseline.f1

  return (
    <article className="prose stack">
      <header>
        <h1>Methods</h1>
        <p className="muted">
          Updated {formatDate(data.generated_at.slice(0, 10))}. These are the current detection
          settings and evaluation results.
        </p>
      </header>

      <section>
        <h2>Detection</h2>
        <p>
          Each day, WikiPulse starts from the top 1000 English Wikipedia articles by pageviews. It
          keeps new entrants, large rank movers and articles on the recent spike watch list, then
          fetches per-article history. A spike must clear a robust z-score of{' '}
          <strong>{data.detector.z_threshold}</strong> and a views floor of{' '}
          <strong>{data.detector.minimum_views.toLocaleString('en-US')}</strong>.
        </p>
        <p>
          The z-score uses the median and median absolute deviation of the previous 28 days, with a
          day-of-week adjustment. Missing days are excluded from the baseline, never filled in.
        </p>
      </section>

      <section>
        <h2>Classifier</h2>
        {data.classifier ? (
          <>
            <p>
              Model: <strong>{data.classifier.model}</strong>, trained on{' '}
              <strong>{data.classifier.labels}</strong> human labels. Evaluation uses
              expanding-window time-series validation, never random splits.
            </p>
            {classifierWeaker ? (
              <div className="notice">
                This classifier does not beat the rule baseline. It is not used to score events yet;
                the rule score remains. More non-event labels are needed.
              </div>
            ) : null}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Event F1</th>
                    <th>Macro F1</th>
                    <th>Brier score</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{data.classifier.event_f1.toFixed(3)}</td>
                    <td>{data.classifier.macro_f1.toFixed(3)}</td>
                    <td>{data.classifier.brier.toFixed(3)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            {baselines.length ? (
              <div className="table-wrap">
                <h3>Baselines</h3>
                <table>
                  <thead>
                    <tr>
                      <th>Baseline</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>F1</th>
                    </tr>
                  </thead>
                  <tbody>
                    {baselines.map(([name, row]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>{row.precision.toFixed(3)}</td>
                        <td>{row.recall.toFixed(3)}</td>
                        <td>{row.f1.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        ) : (
          <div className="notice">
            <p>
              No classifier is trained yet. Labels are added by hand before training, and the
              rule-based score is what the site shows. There are <strong>{data.labels}</strong>{' '}
              labels. {300 - data.labels > 0 ? `${300 - data.labels} more are needed.` : ''}
            </p>
          </div>
        )}
      </section>

      <section>
        <h2>Labels</h2>
        <p>
          {data.labels} labels are available across classes:{' '}
          {data.classes.length ? data.classes.join(', ') : 'none yet'}. The target is at least 300
          labels covering all classes, sampled across the available days.
        </p>
      </section>

      <section>
        <h2>Limitations</h2>
        <ul>
          {data.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>
    </article>
  )
}
