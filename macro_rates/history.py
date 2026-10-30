"""Licensed-contract diagnostics. All outputs from this entry point stay private."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .policy import calendar_ledger, Funding


def historical_contracts(input_dir, output):
    root, out = Path(input_dir), Path(output)
    out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(root/'rates_quotes.csv.gz',dtype={'contrdate':str})
    source_rows=len(raw)
    # The vendor wide view multiplies rows through unrelated auxiliary field p.
    # Collapse only identical consumed observations; conflicting marks still fail.
    used=['contrcode','futcode','dsmnem','contrdate','date_','settlement','volume','openinterest']
    raw=raw[used].drop_duplicates().reset_index(drop=True)
    meta = pd.read_csv(root/'rates_metadata.csv',parse_dates=['lasttrddate'],dtype={'contrdate':str})
    meta['month'] = meta.lasttrddate.dt.to_period('M').astype(str)
    raw['date_'] = pd.to_datetime(raw.date_)
    raw=raw.merge(meta[['futcode','month']],on='futcode',validate='many_to_one')
    if raw.duplicated(['contrcode','futcode','date_']).any():
        raise ValueError('Duplicate vendor contract-day key; review source mapping')
    # Composite chosen for declared coverage, never for its returns. Keep electronic
    # observations as an independent agreement check, not a silent gap splice.
    x=raw.loc[raw.contrcode==3351].copy()
    invalid=x.loc[x.settlement.isna()]
    invalid.to_csv(out/'excluded_missing_marks.csv',index=False)
    x=x.loc[x.settlement.notna()]
    electronic=raw.loc[raw.contrcode==460,['month','date_','settlement']].rename(columns={'settlement':'electronic'})
    compared=x[['month','date_','settlement']].merge(electronic,on=['month','date_'],validate='one_to_one')
    compared['difference']=compared.settlement-compared.electronic
    compared.to_csv(out/'source_agreement.csv',index=False)
    # Realized month averages are evaluation labels, never features for entry.
    effr=pd.DataFrame(json.loads((root/'effr.json').read_text())['refRates'])
    effr['date']=pd.to_datetime(effr.effectiveDate)
    daily=effr.set_index('date').percentRate.sort_index().resample('D').ffill()
    realized=daily.groupby(daily.index.to_period('M')).agg(['mean','count'])
    forecasts=[]
    for month,g in x.groupby('month',sort=True):
        p=pd.Period(month,'M')
        if p not in realized.index or realized.loc[p,'count']!=p.days_in_month:
            continue
        for horizon in [1,3,6]:
            observation=(p-horizon).start_time
            selected=g.loc[g.date_.between(observation,observation+pd.offsets.MonthEnd(0))]
            if selected.empty:continue
            row=selected.sort_values('date_').iloc[-1]
            forecasts.append({'delivery_month':month,'horizon_months':horizon,'observation_date':row.date_,
                              'label_available_no_earlier_than':p.end_time.normalize()+pd.Timedelta(days=1),
                              'implied_percent':100-row.settlement,'realized_percent':realized.loc[p,'mean'],
                              'error_bp':((100-row.settlement)-realized.loc[p,'mean'])*100,
                              'volume_at_observation':row.volume})
    forecasts=pd.DataFrame(forecasts)
    forecasts.to_csv(out/'implied_vs_realized.csv',index=False)
    trades=[];ledgers=[];failures=[]
    for observation in pd.period_range('2010-01','2025-12',freq='M'):
        near,far=str(observation+2),str(observation+5)
        a=x.loc[x.month==near,['date_','settlement','volume']].rename(columns={'settlement':'near','volume':'near_volume'})
        b=x.loc[x.month==far,['date_','settlement','volume']].rename(columns={'settlement':'far','volume':'far_volume'})
        pair=a.merge(b,on='date_',validate='one_to_one')
        pair=pair.loc[pair.date_.dt.to_period('M')==observation].sort_values('date_').rename(columns={'date_':'date'})
        if len(pair)<2:
            failures.append({'observation_month':str(observation),'reason':'insufficient_common_marks','rows':len(pair)})
            continue
        for direction in [1,-1]:
            account=calendar_ledger(pair,direction,Funding())
            account['observation_month']=str(observation);account['direction']=direction
            ledgers.append(account)
            trades.append({'observation_month':str(observation),'direction':direction,'near':near,'far':far,
                           'net_pnl_usd':account.cash.iloc[-1]-100000,
                           'min_cash':account.cash.min(),'max_cash_shortfall':account.cash_shortfall.max(),
                           'zero_volume_days':int(((pair.near_volume<=0)|(pair.far_volume<=0)).sum()),
                           'status':account.status.iloc[-1]})
    trades=pd.DataFrame(trades);ledger=pd.concat(ledgers,ignore_index=True)
    trades.to_csv(out/'monthly_controls.csv',index=False);ledger.to_csv(out/'daily_ledgers.csv',index=False)
    pd.DataFrame(failures).to_csv(out/'failures.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for horizon,g in forecasts.groupby('horizon_months'):
        axes[0].plot(pd.to_datetime(g.delivery_month,format='%Y-%m'),g.error_bp,label=f'{horizon}m')
    axes[0].axhline(0,color='gray',lw=.6);axes[0].legend()
    axes[0].set(title='Implied minus realized monthly EFFR',ylabel='bp; includes premia and forecast error')
    for direction,g in trades.groupby('direction'):
        axes[1].plot(pd.to_datetime(g.observation_month),g.net_pnl_usd,label=f'direction {direction:+d}')
    axes[1].legend();axes[1].set(title='Fixed calendar controls, separate USD 100k accounts',ylabel='Monthly model P&L after cost proxies (USD)')
    fig.savefig(out/'private_policy_history.png',dpi=160);plt.close(fig)
    summary={'status':'private exploratory reference; not licensed for public release',
             'source_wide_rows':source_rows,'canonical_rows':len(raw),
             'identical_consumed_rows_collapsed':source_rows-len(raw),
             'composite_rows':len(x),'electronic_rows':int((raw.contrcode==460).sum()),
             'source_comparison_rows':len(compared),'source_disagreements_over_half_tick':int((compared.difference.abs()>.0025).sum()),
             'maximum_source_difference':float(compared.difference.abs().max()),
             'forecast_labels':len(forecasts),'monthly_accounts':len(trades),'missing_months':failures,
             'maximum_ledger_error':float(ledger.reconciliation_error.abs().max()),
             'unit_status':'Composite unitcode is absent. Contract identity and near-100 quote convention are corroborated; original vendor unit definition not yet independently documented. Blocks unit-verified trading claim.',
             'fill_status':'Settlement-to-settlement mark controls; no executable quote/liquidity guarantee',
             'history_status':'Current metadata and historical vintage, not full point-in-time',
             'margin_status':'USD 2000/contract proxy, no offset; dated historical broker margin absent',
             'input_sha256':hashlib.sha256((root/'rates_quotes.csv.gz').read_bytes()).hexdigest()}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2))
    (out/'REPORT_CN.md').write_text('# Fed Funds 私有历史审计\n\n'
        '本报告采用有完整目标日期覆盖的复合系列。电子盘不与它拼接；全部跨源差异保留。'
        '复合系列缺少原始单位字段，因此本次可做探索性报价与账本核对，不能称为单位和许可均验收通过的可交易研究。\n\n'
        '市场隐含月均利率减最终实现值同时包含预测误差、风险溢价及时间／基准差异，不是无风险套利。'
        '月度正反两方向均报告，未选赢家；每月新设同额账户，不把独立账本拼成复利净值。'
        '零成交量日和缺失月份保留，结算价不是成交价。\n\n```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
    return summary
