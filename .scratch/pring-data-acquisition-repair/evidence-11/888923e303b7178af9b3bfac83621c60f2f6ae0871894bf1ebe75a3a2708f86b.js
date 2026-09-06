/*
 * @Description: 引用的文件路径，统一维护
 * @Author: zhou.xiaowei@trs.com.cn
 * @Date: 2023-08-31 08:56:30
 */

// 品种配置信息
function api_shfe_product_config() {
  return '/data/config/product_config.dat?params=' + new Date().getTime();;
}

// 品种配置信息
function api_shfe_web_config() {
  return '/data/config/web_config.dat?params=' + new Date().getTime();;
}

// 品种配置信息--  language: 中文 cn 、英文en
function api_shfe_report_config(language) {
  const report_config_cn = '/data/config/report_config_cn.dat?params=' + new Date().getTime();; // 报表配置中文
  const report_config_en = '/data/config/report_config_en.dat?params=' + new Date().getTime();; // 报表配置英文
  return language === enumObj.language.en ? report_config_en : report_config_cn;
}

// 交易日历维护
function api_cms_calendar(date) {
  let newdate = date.substring(0, 4)
  return '/data/calendar/calendar_'+newdate+'.dat?params=' + new Date().getTime();;
}


// --- 期货-日报

// 组保参数查询-商品组信息
function api_future_combCommodity(date) {
  return '/data/busiparamdata/portfolio/CombCommodity' + date + '.dat?params=' + new Date().getTime();;
}

// 组保参数查询-组保业务参数
function api_futures_paramCategory(date) {
  return '/data/busiparamdata/portfolio/ParamCategory' + date + '.dat?params=' + new Date().getTime();;
}

// 大笔交易-实时行情
function api_futures_blocktrade(date) {
  return '/data/blockdata/blocktrade' + date + '.dat?params=' + new Date().getTime();;
}

// 大笔交易-意向申报
function api_futures_blockintention(date) {
  return '/data/blockdata/blockintention' + date + '.dat?params=' + new Date().getTime();;
}

// 行情交易日期查询
function api_futures_blockTradeTradingday () {
  return  '/data/blockdata/blockTradeTradingday.dat'
}

// 大笔交易-逐笔行情
function api_futures_blockdata(date) {
  return '/data/blockdata/blockdata' + date + '.dat?params=' + new Date().getTime();;
}

// 大笔交易-月度行情
function api_futures_blockmonthstat(date) {
  let blockmonthstat_date = date.substring(0, 6);
  return '/data/blockdata/blockmonthstat' + blockmonthstat_date + '.dat?params=' + new Date().getTime();;
}

// 期货-日交易快讯
function api_futures_kx(date) {
   return '/data/tradedata/future/dailydata/kx' + date + '.dat?params=' + new Date().getTime();;

}
// 期货-日交易排名
function api_futures_pm(date) {
   return '/data/tradedata/future/dailydata/pm' + date + '.dat?params=' + new Date().getTime();;
  

}
// 期货-日间均价-当前合约加权平均价
function api_futures_defaultTimePrice(date) {
  return '/data/tradedata/future/dailydata/' + date + 'defaultTimePrice.dat?params=' + new Date().getTime();;
}
// 期货-日间均价-主力合约加权平均价
function api_futures_mainTimePrice(date) {
  return '/data/tradedata/future/dailydata/' + date + 'mainTimePrice.dat?params=' + new Date().getTime();;
}
// 期货-日间均价-各品种合约加权平均价
function api_futures_dailyTimePrice(date) {
  return '/data/tradedata/future/dailydata/' + date + 'dailyTimePrice.dat?params=' + new Date().getTime();;
}
// 期货-日中交易参考价
function api_futures_markerprice(date) {
	return '/data/tradedata/future/dailydata/' + date + 'markerprice.dat?params=' + new Date().getTime();;
 
}
// 期货-日间均价（当前合约加权平均价）
function api_futures_timeprice_default(date) {
	return '/data/tradedata/future/dailydata/' + date + 'defaultTimePrice.dat?params=' + new Date().getTime();;

}
// 期货-日间均价（主力合约加权平均价）
function api_futures_timeprice_main(date) {
	return '/data/tradedata/future/dailydata/' + date + 'mainTimePrice.dat?params=' + new Date().getTime();;
 
}
// 期货-日间均价（各品种合约加权平均价）
function api_futures_timeprice_daily(date) {
	return '/data/tradedata/future/dailydata/' + date + 'dailyTimePrice.dat?params=' + new Date().getTime();;

}
// 期货-每日结算参数
function api_futures_js_f(date) {
   return '/data/tradedata/future/dailydata/js' + date + '.dat?params=' + new Date().getTime();;
}
// 期货-仓单日报
function api_futures_dailystock(date) {
   return '/data/tradedata/future/dailydata/' + date + 'dailystock.dat?params=' + new Date().getTime();;
}

// 期货-仓单日报-老数据
function api_future_dailystock_html(date) {
  return '/data/tradedata/future/dailydata/' + date + 'dailystock.html?params=' + new Date().getTime();;
}


// 期货-厂库提货地升贴水
function api_futures_dailydlvplacepremium(date) {
	 return '/data/tradedata/future/dailydata/' + date + 'dailydlvplacepremium.dat?params=' + new Date().getTime();;
}
// 期货-仓单货位查询-列表
function api_futures_stock_data_list() {
   return '/data/tradedata/future/dailydata/stock_data_list.dat?params=' + new Date().getTime();;
}

// 期货-仓单货位查询-品种数据  (示例：/stock_ag_20230808.dat )
function api_futures_stock_data(productId, date) {
   return '/data/tradedata/future/dailydata/stock_' + productId + '_' + date + '.dat?params=' + new Date().getTime();;
}

// --- 期货-周报
// 期货-每周行情
function api_future_week(date) {
  return '/data/tradedata/future/weeklydata/' + date + '.dat?params=' + new Date().getTime();;
 
}
// 期货-库存周报-新数据
function api_future_weeklystock(date) {
	return '/data/tradedata/future/weeklydata/' + date + 'weeklystock.dat?params=' + new Date().getTime();;
}

// 期货-库存周报-老数据
function api_future_weeklystock_html(date) {
  return '/data/tradedata/future/weeklydata/' + date + 'weeklystock.html?params=' + new Date().getTime();;
}

// --- 期货-月报
// 期货-月度统计
function api_future_monthvarietystatistics(date) {
  let monthvarietystatistics_date = date.substring(0, 6);
  return '/data/tradedata/future/monthdata/' + monthvarietystatistics_date + 'monthvarietystatistics.dat?params=' + new Date().getTime();;
}
// 期货-月度统计-iframe
function api_future_monthvarietystatistics_html(date) {
  let monthvarietystatistics_date = date.substring(0, 6);
  return '/data/tradedata/future/monthdata/' + monthvarietystatistics_date + 'monthstat.html';
}

// 期货-月度参考价
function api_future_monthprice_day(date) {
	return '/data/tradedata/future/monthdata/' + date + 'price.dat?params=' + new Date().getTime();;
}

// 期货-月度参考价
function api_future_monthprice_month(date) {
  let url = date.substring(0, 6)
 return '/data/tradedata/future/monthdata/' + url + 'price.dat?params=' + new Date().getTime();;
}


// 期货-每月行情-日
function api_future_month_day(date) {
	 return '/data/tradedata/future/monthdata/' + date + 'month.dat?params=' + new Date().getTime();;
}

// 期货-每月行情--月
function api_future_month_month(date) {
  let url = date.substring(0, 6)
   return '/data/tradedata/future/monthdata/' + url + 'month.dat?params=' + new Date().getTime();;
}

// 期货-交割查询
function api_future_exchangeDelivery_f(date) {
  let exchangeDelivery_date = date.substring(0, 6);
   return '/data/tradedata/future/monthdata/ExchangeDelivery' + exchangeDelivery_date + '.dat?params=' + new Date().getTime();;
}
// 期货-月均结算价
function api_future_mosPrice(date) {
  let exchangeDelivery_date = date.substring(0, 6);
  return '/data/tradedata/future/monthdata/' + exchangeDelivery_date + 'mosPrice.dat?params=' + new Date().getTime();;
}
// 期货-月均结算价-年度数据下载
function api_future_yearlyMosPrice(date) {
  let datemonth = date.substring(0, 6)
   return '/data/tradedata/future/monthdata/' + datemonth + 'yearlyMosPrice.dat?params=' + new Date().getTime();;
}
// --- 期货-年报
// 期货-年度统计数据
function api_future_year_f(date) {
  let year_date = date.substring(0, 4);
  return '/data/tradedata/future/yeardata/' + year_date + 'year.dat?params=' + new Date().getTime();;
}
// 期货-年度统计数据下载 (示例： MarketData_Year_2022year.zip )
function api_future_year_download(date) {
  return '/data/tradedata/future/yeardata/MarketData_Year_' + date + '.zip?params=' + new Date().getTime();;
}
// 期货-合约参数
function api_future_currinstrumentprop_f(date) {
   return '/data/busiparamdata/future/ContractBaseInfo' + date + '.dat?params=' + new Date().getTime();;
}
// 期货-交易参数
function api_future_trading_daily_f(date) {
   return '/data/busiparamdata/future/ContractDailyTradeArgument' + date + '.dat?params=' + new Date().getTime();;
}
// 期货-结算参数
function  api_option_settlement_f(date) {
	return '/data/busiparamdata/future/Settlement' + date + '.dat?params=' + new Date().getTime();;
}
// 期货-交割参数
function api_future_delivery(date) {
	return '/data/busiparamdata/future/Delivery' + date + '.dat?params=' + new Date().getTime();;
}

// 期货-延时行情
function api_futures_delaymarket_f(productId) {
  return '/data/tradedata/future/delaymarket/delaymarket_'+productId+'.dat?params=' + new Date().getTime();;
}

// 期货-延时行情
function api_futures_delaymarket_config(productId) {
	 return '/data/tradedata/future/delaymarket/'+productId +'.dat?params=' + new Date().getTime();;
}

// --- 期权-日报

// 期权-延时行情
function api_futures_delaymarket_o(productId) {
 
  return '/data/tradedata/option/delaymarket/delaymarket_'+productId+'Q'+'.dat?params=' + new Date().getTime();;
 
}

// 期权-日交易快讯
function api_futures_kxq(date) {
  return '/data/tradedata/option/dailydata/kx' + date + '.dat?params=' + new Date().getTime();;
}


//期权每日结算参数
function api_option_jsq(date) {
  return '/data/tradedata/option/dailydata/js' + date + '.dat?params=' + new Date().getTime();;
}

// 期权-结算参数 
function api_option_settlement(date) {
	return '/data/busiparamdata/option/Settlement' + date + '.dat?params=' + new Date().getTime();;
}
// 期权-交易参数
function api_option_tradingdaily_js(date) {
	return '/data/busiparamdata/option/ContractDailyTradeArgument' + date + '.dat?params=' + new Date().getTime();;
}

// 期权-合约参数
function api_future_currinstrumentprop (date) {
  return '/data/busiparamdata/option/ContractBaseInfo' + date + '.dat?params=' + new Date().getTime();;
}
// --- 期权-周报
// 期权-每周行情
function api_option_week(date) {
 return '/data/tradedata/option/weeklydata/' + date + '.dat?params=' + new Date().getTime();;
}
// --- 期权-月报
// 期权-月度统计
function api_option_monthvarietystatistics(date) {
  let monthvarietystatistics_date = date.substring(0, 6);
  return '/data/tradedata/option/monthdata/' + monthvarietystatistics_date + 'monthvarietystatistics.dat?params=' + new Date().getTime();;
}

// 期权-月度统计
function api_option_monthvarietystatistics_html(date) {
  let monthvarietystatistics_date = date.substring(0, 6);
  return '/data/tradedata/option/monthdata/' + monthvarietystatistics_date + 'monthstat.html?params=' + new Date().getTime();;
}



// 每月行情-期权-天
function api_option_monthq_day(date) {
  return '/data/tradedata/option/monthdata/' + date + 'month.dat?params=' + new Date().getTime();;
}

// 每月行情-期权-月
function api_option_monthq_month(date) {
  let monthq_date = date.substring(0, 6);
  return '/data/tradedata/option/monthdata/' + monthq_date + 'month.dat?params=' + new Date().getTime();;
}

// --- 期权-年报
// 期权-年统计数据 (示例： /2022optionyear.dat )
function api_option_year_o(date) {
  let year_date = date.substring(0, 4);
  return '/data/tradedata/option/yeardata/' + year_date + 'optionyear.dat?params=' + new Date().getTime();;
}
// 期权-年度统计数据下载
function api_option_year_download(date) {
  return '/data/tradedata/option/yeardata/MarketData_Year_' + date + '.zip?params=' + new Date().getTime();;
}



//  指数日行情A
function api_option_dayA(date) {
  return '/data/tradedata/shfeindexdata/shfeci-'+date+'-all-kline.dat?params=' + new Date().getTime();;
}

//  指数日行情B
function api_option_dayB(date) {
	return '/data/tradedata/shfeindexdata/shfeci-'+date+'-all-latest.dat?params=' + new Date().getTime();;
}

//  指数日行情C
function api_option_dayC(cate) {
	return '/data/tradedata/shfeindexdata/shfeci-all-'+cate+'-kline.dat?params=' + new Date().getTime();;
}

//  指数日行情D
function api_option_dayD(date, cate) {
	return '/data/tradedata/shfeindexdata/shfeci-'+date+'-'+cate+'-line.dat?params=' + new Date().getTime();
}

// 指数行情分时
function api_all_timeline(paramdate) {
	return '/data/tradedata/shfeindexdata/shfeci-'+paramdate+'-all-timeline.dat?params=' + new Date().getTime();
}

// 指数行情分时
function api_shfeci_line(paramdate, indexId) {
	return "/data/tradedata/shfeindexdata/shfeci-" + paramdate + "-" + indexId + "-line" + ".dat?params=" + new Date().getTime();
}

// 指数行情分时
function api_shfeci_all_line(indexId) {
  return "/data/tradedata/shfeindexdata/shfeci-all-" + indexId + "-kline" + ".dat?params=" + new Date().getTime();
}
//  上期月度成交概况
function api_shfe_month(date) {
  let monthq_date = date.substring(0, 6);
  return '/data/tradedata/future/monthdata/'+monthq_date + 'monthlyShfeTradeOver.dat?params=' + new Date().getTime();
}

//  能源月度成交概况
function api_ine_month(date) {
  let monthq_date = date.substring(0, 6);
   return '/data/tradedata/future/monthdata/'+monthq_date + 'monthlyIneTradeOver.dat?params=' + new Date().getTime();
}


// 期货-交易综述
function api_futures_trade_des() {
  return `/reports/tradedata/dailyandweeklydata/transactionsummary_f/transaction.json?params=` + new Date().getTime();
}

// 期权-交易综述
function api_options_trade_des() {
  return `/reports/tradedata/dailyandweeklydata/transactionsummary_o/transaction.json?params=` + new Date().getTime();
}


// 日历上小红点
function api_trade_data() {
  return "/data/config/js/trade-data.js?params=" + new Date().getTime()
}

// 首页和交易日历上的小红点
function api_calendar_data() {
  return "/data/config/js/calendar-data.js?params=" + new Date().getTime()
}

// 当前交易日
function api_trade_date() {
  return "/data/config/currentTradingday.dat?params=" + new Date().getTime();
}


// ISIN
function api_ISIN_code(year) {
  return "/data/isincode/isincode_" + year +'.dat?params=' + new Date().getTime();
}

// 会员名单
function api_about_member() {
  return "/data/member/member.dat?params=" + new Date().getTime();
}

// 产品--行情走势
function api_production_line(params) {
  return '/data/tradedata/future/delaymarket/delayed_market_data_' + params + '_history.dat?params="' + new Date().getTime();
}

// --- 动态交互 -------------------------
// 廉洁从业监督---举报
function api_saveImpeachment(params) {
  return '/dynawebInet/saveImpeachment';
}
// 廉洁从业监督---查询举报信息
function api_searchImpeachment(params) {
  return '/dynawebInet/getImpeachment';
}
// 结算交割员考试---期次
function api_getElearning(params) {
  return '/dynawebInet/getElearningList';
}
// 结算交割员考试---提交
function api_saveSignup(params) {
  return '/dynawebInet/saveSignup';
}
// 结算交割员考试---查询考试结果
function api_searchExamSignup(params) {
  return '/dynawebInet/getSignup';
}


// 境外中介
function api_sea_member() {
  return "/data/member/overseasagency.dat?params=" + new Date().getTime();
}


//仓单日报 iframe 获取地址
function api_dailystock_iframe(date,productid,exchangeid){
	if(productid==='all'){
		return '/data/tradedata/future/stockdata/dailystock_'+date+'/ZH/'+productid+'.html?params=' + new Date().getTime();
	}else{
		return '/data/tradedata/future/stockdata/dailystock_'+date+'/ZH/'+exchangeid+'/'+productid+'.html?params=' + new Date().getTime();
	}	
}

//库存周报 iframe 获取地址
function api_weeklystock_iframe(date,productid,exchangeid){
	if(productid==='all'){
	return '/data/tradedata/future/stockdata/weeklystock_'+date+'/ZH/'+productid+'.html?params=' + new Date().getTime();
	}else{
		return '/data/tradedata/future/stockdata/weeklystock_'+date+'/ZH/'+exchangeid+'/'+productid+'.html?params=' + new Date().getTime();	
	}	
}

//厂库提货地升贴水 iframe 获取地址
function api_dlvplacepremium_iframe(date,productid,exchangeid){
	if(productid==='all'){
		return '/data/tradedata/future/stockdata/dlvplacepremium_'+date+'/ZH/'+productid+'.html?params=' + new Date().getTime();
	}else{
		return '/data/tradedata/future/stockdata/dlvplacepremium_'+date+'/ZH/'+exchangeid+'/'+productid+'.html?params=' + new Date().getTime();	
	}	
}
//期货-套利合约参数：
function api_getSpreadOrder(date){
 return '/data/busiparamdata/future/SpreadOrder' + date + '.dat?params=' + new Date().getTime();
}