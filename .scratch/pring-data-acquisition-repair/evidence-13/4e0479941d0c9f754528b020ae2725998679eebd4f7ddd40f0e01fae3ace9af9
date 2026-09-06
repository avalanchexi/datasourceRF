var aaa="=YnQq5ENWZUZzZFWRxGazUFTS1mT";var bbb="==AO3QVZSV0VzkWNYdjSwhjW";$.ajaxSetup({tryCount:0,retryLimit:1,error:function(a){this.tryCount++;if(this.tryCount<=this.retryLimit){$.ajax(this);return}}});var ccc=helper(bbb);$.ajax({url:"/dqs/rest/cm-u-rbt/apply",type:"POST",dataType:'json',cache:false,data:{"key":ccc}});function helper(a){return a.split('').reverse().join('')};
// JavaScript Document
//市场公告>评级公告>历史评级变动-变动方向
var cgOfRt = ["首次","上调","下调","维持"];
//评级方式
var rtngMthd = ["--","首次评级","跟踪评级"];

//add by mbl v3.159.0 start ---------------
//计算机构
var calcAgntArr = ["---","中国外汇交易中心","交易双方","买入方","卖出方","---","第三方","---","---","其他"];
//信用事件
var crdtEvArr = ["---","破产","支付违约","债务加速到期","债务违约","偿付变更","其他","债务重组","债务潜在加速到期"];
//违约结算方式
var brchStlmntMthdArr = ["---","实物结算","现金结算","其他","拍卖结算"];
//收费方式
var chrgngMthdsArr = ["---","前端一次性收费","按年付费","按季付费","其他"];
//add by mbl v3.159.0 end ---------------

//日报时刻点
//同业拆借
var IBLR_PUBLISHED_TIME = 2200;
//质押式回购
var PR_PUBLISHED_TIME = 2200;
//买断式回购
var OR_PUBLISHED_TIME = 2200;
//现券买卖
var CBT_PUBLISHED_TIME = 2200;
//标准债券远期
var BFWD_PUBLISHED_TIME = 2200;
//利率互换
var IRS_PUBLISHED_TIME = 2200;
//债券借贷
var BDC_PUBLISHED_TIME = 2200;

//历史稿件设置默认字体及大小时间节点
var timeNode = '2020-05-01 23:59:59';

//@{res}
var RESURL = '';

// 默认路径
var JURL = '',                  // 子页面
    DURL = '/r/cms/www/chinamoney/data/',          // 数据
    MURL = '/r/cms/chinese/chinamoney/assets/';        // 媒体资源

var CDURL = '/r/cms/chinese/chinamoney/data/';//中文版数据

var AGSMS = '/dqs/rest/',//微服务se
    DQSURL = '/dqs/rest/';//dqs

var BK_URL = '/ags/ms/',
    NT_URL = '/ags/ms',
    MD_URL = '/ags/ms/',
    //LSS_URL = 'http://testwww.chinamoney.com.cn/lss/rest/';
LSS_URL = '/lss/rest/';
var SES_URL = '/ses/rest';
var DURL_TEST= '/r/cms/www/chinamoney/data/';


var FREQUESTIP;
var FREQUESTURL;
var BLACKVALIDATEOPEN = false;

    var u=navigator.userAgent.toLowerCase();
    var browser={versions:function(){
        return{
        pc: u.indexOf('windows nt') > -1,  
        linux: u.indexOf('linux') > -1, 
        android:u.indexOf('android')>-1,
        Phone:u.indexOf('iphone')>-1||u.indexOf('ipod')>-1||u.indexOf('itouch')>-1||u.indexOf('windows phone') > -1,
        iPad :u.indexOf('macintosh')>-1 && window.innerWidth<=1024};}()
    };
    if(browser.versions.Phone){
       DURL = '/r/cms/www/chinamoney/data/';
    } else if(browser.versions.iPad){
       DURL = '/r/cms/www/chinamoney/data/';
    } else if (browser.versions.android){
       DURL = '/r/cms/www/chinamoney/data/';
    }
    //alert(u + browser.versions.android + "" +DURL+window.innerWidth);

//稿件图标下载URL
var fileDownUrl = '/dqs/cm-s-notice-query/';


var DOC = window.document,
    // 视域、尺寸相关
    V_VP, V_VW, V_VH, V_MW,
    _V_VW, _V_VH,
    // 像素比
    V_DPR,
    // 浏览器代理字符串
    BROWSER_AGENT = navigator.userAgent,
    // 触控事件支持
    HASTOUCH = 'ontouchend' in DOC.documentElement ? true : false,
    STANDBY_ELEMENT = 'header',
    READY_GO = false,
    // 顶层元素
    TOP_DIV = '#main-page',
    TOP_ELEMENT = HASTOUCH ? TOP_DIV : DOC,
    // 默认点击事件名
    DEFAULT_EVENT = HASTOUCH ? 'touchend' : 'click',
    // 媒体响应区间
    MEDIA_RULE,
    // 媒体区间方案标记
    MEDIA_CASE = '',
    // 媒体监听标记
    MEDIA_LISTENER = 'mediaListener',
    MEDIA_LISTENER_GROUP,
    RESIZE_LISTENER = 'resizeListener',
    RESIZE_LISTENER_GROUP,
    SCROLL_LISTENER_GROUP,
    // 滚动条尺寸
    SSZ = 0,
    // IE版本号
    IE_V = -1,
    GLOBE_INIT = false,
    RESIZE_IGNORE = false,
    // 频道数据
    DATA_CHANNEL,
    STORAGE_CHANNEL; 

var MONTH = new Array('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'),
    MONTHSHORT = new Array('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec');
var WEEK = new Array('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'),
    WEEKSHORT = new Array('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat');

// 仅用于htmlDEMO
var ROUTE = {
        'home': 'home',                                 // 首页
        'disclosure': 'disclosure',                     // 披露
        'market-data': 'market-data',                   // 数据
        'self-discipline': 'self-discipline',           // 自律
        'benchmarks': 'benchmarks',                     // 基准
        'service': 'service',                           // 服务
        'about-us': 'about-us',                         // 关于
        'signin': 'signin',
        'search': 'search',
        'feature': 'feature'
    },
    ROUTE_MAP,
    // 注入替换变量。属性名不能带有.
    injectedObj = {
        'JURL': JURL,
        'MURL': MURL,
        'DURL': DURL,
        'CHANNEL': ROUTE
    };

// window.localStorage.removeItem('channel');

// 页面初始化
$(function(){
    var $doc = $('html'),
        mediaList,
        $base = null, $navi = null, $naviList = null,
        naviWidth = null, blank = null,
        aniTimer = null;
    var initTimer = setInterval(function(){
        if ('san' in window) {
            clearInterval(initTimer);
            V_DPR = san.view.dpr();
            IE_V = san.browser.ieAgent();

            ROUTE_MAP = san.tools.objectCreate(null);
            MEDIA_RULE = san.tools.objectCreate(null);
            // 均表示当前尺寸的最小值
            MEDIA_RULE.XS = 0;
            MEDIA_RULE.S = 576;
            MEDIA_RULE.M  = 768;
            MEDIA_RULE.L  = 992;
            MEDIA_RULE.XL  = 1230;
            mediaList = [MEDIA_RULE.XS, MEDIA_RULE.S, MEDIA_RULE.M, MEDIA_RULE.L, MEDIA_RULE.XL, 10000];

            MEDIA_LISTENER_GROUP = san.tools.objectCreate(null);
            RESIZE_LISTENER_GROUP = san.tools.objectCreate(null);
            SCROLL_LISTENER_GROUP = san.tools.objectCreate(null);
            
            if (~IE_V && IE_V < 9) {
                document.createElement('template');
            }

            var _initTimer = setInterval(function(){
                if (READY_GO) {
                    clearInterval(_initTimer);
                    $base = $('#' + STANDBY_ELEMENT);
                    $navi = $('#fixed-navi');
                    //$naviList = $('#fixed-navi-qrcode');
                    $(window).trigger('resize.init', [0]);
                    
                    var $headerToTop = $('#header-handle-to-top');
                    $(window).on('scroll.init', san.tools.throttle(function(){
                        if ($('#main-page-menu').hasClass('handle-active')){return;}
                        $base.outerHeight(true) < san.view.scroll().top ? $headerToTop.addClass('active') : $headerToTop.removeClass('active');
                    }, 300));

                    /*if (!$naviList.attr('data-status') || $naviList.attr('data-status') !== 'done') {
                        $naviList.html('<template><li *san-for="item in records"><a href="{{#item.url}}" target="_blank"><img src="{{#item.imgSrc}}"></a><div class="text">{{#item.text}}</div></li></template>');
                        $naviList.sanTemplate({
                            data: data_qrcode,
                            onDone: function(){
                                $(this).attr('data-status', 'done');
                            },
                            onFail: function(){
                                $(this).attr('data-status', 'fail');
                            }
                        });
                    }*/
                }
            }, 10);
        }
    }, 10);
    
    $(window).on('resize.init', function(e, duration) {
        //clearTimeout(initTimer);
        clearTimeout(aniTimer);
        GLOBE_INIT = false;
        RESIZE_IGNORE = false;

        if (!READY_GO) { return; }

        duration = typeof duration !== 'undefined' && san.tools.type(duration) === 'number' ? duration : 150;

        initTimer1 = setTimeout(function(){
            _V_VW = V_VW;
            _V_VH = V_VH;
            V_VP = san.view.viewport();
            V_VW = V_VP.width;
            V_VH = V_VP.height;
            V_MW = san.view.rect($base[0]).width;
            SSZ = san.browser.scrollDetector();
            
            if (_V_VW === V_VW) {
                RESIZE_IGNORE = true;
            }

            naviWidth = $navi.outerWidth();
            blank = V_VW - V_MW;

            if (V_VW >= MEDIA_RULE.M) {
                aniTimer = setTimeout(function(){
                    $navi.addClass('active');
                    if (blank * 0.5 - 25 >= naviWidth + 25) {
                        $navi.css('right', blank * 0.5 - 25 - naviWidth + 'px');
                    } else {
                        $navi.css('right', 0);
                    }
                }, 100);
            } else {
                $navi.removeClass('active').removeAttr('style');
            }
            
            var mediaHit = san.tools.grep(mediaList, function(e, i){
                    if (V_VW >= e && V_VW < mediaList[i + 1]) {
                        return true;
                    }
                })[0],
                curMedia = (curMedia = MEDIA_CASE) ? MEDIA_RULE[curMedia.toUpperCase()] : '';
            // if (mediaHit !== curMedia || curMedia !== MEDIA_RULE.XL) {
            if (mediaHit !== curMedia) {
                switch (mediaHit) {
                    case MEDIA_RULE.XS:
                        MEDIA_CASE = 'XS';
                        break;
                    case MEDIA_RULE.S:
                        MEDIA_CASE = 'S';
                        break;
                    case MEDIA_RULE.M:
                        MEDIA_CASE = 'M';
                        break;
                    case MEDIA_RULE.L:
                        MEDIA_CASE = 'L';
                        break;
                    default:
                        MEDIA_CASE = 'XL';
                        break;
                }
                $doc.attr('data-media', MEDIA_CASE);
            }
            
            // setTimeout(() => {
            GLOBE_INIT = true;
            // }, 2000);

            //console.log('GOLBE_INIT Finished. HASTOUCH - ' + HASTOUCH + ',  DEFAULT_EVENT - ' + DEFAULT_EVENT + ', V_VW / V_VH / V_MW - ' + V_VW + ' / ' + V_VH + ' / ' + V_MW);

            if (!RESIZE_IGNORE){
                san.listener.mediaQuery();
                san.listener.resizeQuery();
            }

            // #console-panel
            // consolePanelBuild();
        }, duration);
    });
    
    $(DOC).on(DEFAULT_EVENT + '.toTop', '[data-role="to-top"]', function(){
        $("html,body").animate({scrollTop: 0}, 100);
    });

    $(DOC).on(DEFAULT_EVENT + '.fontControl', '.fc-s[data-font]', function(){
        var $f = $(this),
            $target = $f.closest('.article-a').find('.article-a-content'),
            size;
        $f.addClass('active').siblings().removeClass('active');
        size = $f[0].getAttribute('data-font');
        $target[0].style.cssText = 'font-size:' + size + '% !important';
    });

    $(DOC).on(RESIZE_LISTENER + '.sectionDetail', '.section-detail[data-resize="true"]', function(){
        var $this = $(this),
            $item,
            cell0 = 'detail-label', cell1 = 'detail-value',
            $d, $a, $b,
            h, h0, h1;
        if (V_VW < MEDIA_RULE.M) {
            $this.find('.' + cell1).css('height','');
            return;
        }
        
        //$item = $this.find('.detail-item');
	    //add by mbl v3.159.0 start ---------------
        $item = $this.find('.detail-item-half');
	    //add by mbl v3.159.0 end ---------------
        $item.each(function(i){
            $d = $(this);
            $d.find('.' + cell1).css('height','');
            h = Math.max($d.find('.' + cell0).outerHeight(), $d.find('.' + cell1).outerHeight());
            if (san.tools.isEven(i)) {
                $a = $d;
                h0 = h;
            } else {
                $b = $d;
                h1 = h;
                if (h0 != h1) {
                    h = Math.max(h0, h1);
                    $a.find('.' + cell1).css('height', h + 'px');
                    $b.find('.' + cell1).css('height', h + 'px');
                }
            }
        });
    });
    
    $(window).on('scroll.sanDatasheet', function(){
        if (!GLOBE_INIT) { return; }
        if (V_VW >= MEDIA_RULE.M || $('#page-homepage').length) { return; }
        san.listener.scrollQuery();
    });

    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(){
    	this.addEventListener('load',function(){
    		if(this.status == 421 && BLACKVALIDATEOPEN == false){
    			var responseText = this.responseText;
				var str1 = responseText.substring(responseText.indexOf('[')+1,responseText.lastIndexOf(']'));
				FREQUESTIP = str1.substring(0,str1.indexOf(']'));
				FREQUESTURL = str1.substring(str1.indexOf('[')+1);
				popupConfirm('/r/cms/chinese/chinamoney/html/msg-frequest.html');
				BLACKVALIDATEOPEN = true;
    		}
    	});
    	origOpen.apply(this,arguments);
    };
});



function consolePanelBuild() {
    var str = '';
    str += '<div>&gt; HASTOUCH: ' + HASTOUCH + '</div>';
    str += '<div>&gt; DEFAULT_EVENT: ' + DEFAULT_EVENT + '</div>';
    str += '<div>&gt; V_VW / V_VH / V_MW: ' + V_VW + ' / ' + V_VH + ' / ' + V_MW + '</div>';
    if ($('#console-panel').length) {
        $('#console-panel').html(str);
    } else {
        $('body').append('<div id="console-panel">' + str + '</div>');
    }
}



;(function($, undefined) {
    'use strict';
    
    var slice = Array.prototype.slice;
    var concat = Array.prototype.concat;
    var push = Array.prototype.push;
    var indexOfArray = Array.prototype.indexOf;
    var indexOfString = String.prototype.indexOf;
    var toString = Object.prototype.toString;
    var hasOwn = Object.prototype.hasOwnProperty;

    var san = {}

    san.tools = {
        /**
         * 返回一个唯一标识符。
         */
        uuid: function(name) {
            return (name ? '' + name : '') + ('' + Math.random()).replace(/\D/g, '');
        },
        /**
         * 为url添加时间戳
         */
        urlTimestamp: function(url) {  
            var timstamp = (new Date()).valueOf();
            url = (url.indexOf('?') >= 0) ? url + '&t=' + timstamp + '' : url + '?t=' + timstamp;  
            return url;
        },
        contain: function(elem){
            return document.body.contains(elem);
        },
        /**
         * 判断是否是偶数
         */
        isEven: function(n) {
            return (n & 1) ? false : true;
        },
        /**
         * 判断对是否数组
         **/
        isArray: Array.isArray || function( obj ) {
            return this.type(obj) === 'array';
        },
        /**
         * 判断对是否函数
         **/
        isFunction: function(obj) {
            return this.type(obj) === 'function';
        },
        /**
         * 判断对是否是数字
         **/
        isNumeric: function(obj) {
            var realStringObj = obj && obj.toString();
            return !this.isArray(obj) && (realStringObj - parseFloat( realStringObj ) + 1) >= 0;
        },
        /**
         * 判断对是否是window对象
         **/
        isWindow: function(obj) {
            return obj != null && obj == obj.window;
        },
        /**
         * 判断对象是否为空
         **/
        isEmptyObject: function(obj) {
            var name;
            for(name in obj) {
                return false;
            }
            return true;
        },
        /**
         * 在数组中查找指定元素
         * 返回值：数组下标。未找到则返回-1。
         * elem：要查找的值
         * array：在此数组中进行查找
         * i：查找起始位置，默认0
         **/
        inArray: function(elem, arr, i) {
            if (arr) {
                if (indexOfArray) {
                    return indexOfArray.call(arr, elem, i);
                }
                var len;
                len = arr.length;
                i = i ? i < 0 ? Math.max(0, len + i) : i : 0;
                for (; i < len; i++) {
                    if (i in arr && arr[i] === elem) {
                        return i;
                    }
                }
            }
            return -1;
        },
        /**
         * 在数组中查找符合条件的数组元素并返回
         * elems：待查找的数组
         * callback：过滤条件，参数：当前元素和下标，需返回一个Boolean
         * invert: 是否反转，true时返回不符合条件的元素
         **/
        grep: function(elems, callback, invert) {
            var callbackInverse,
                matches = [],
                i = 0,
                len = elems.length,
                callbackExpect = !invert;
            for (; i < len; i++) {
                callbackInverse = !callback(elems[i], i);
                if (callbackInverse !== callbackExpect) {
                    matches.push(elems[i]);
                }
            }
            return matches;
        },
        /**
         * 合并数组。将second并入first。
         * first：必须是数组或类数组对象。
         **/
        merge: function(first, second) {
            var len = +second.length,
                j = 0,
                i = first.length;
            while (j < len) {
                first[i++] = second[j++];
            }
            if (len !== len) {
                while (second[j] !== undefined) {
                    first[i++] = second[j++];
                }
            }
            first.length = i;
            return first;
        },
        /**
         * 创建新对象及其关联
         **/
        objectCreate: function(o) {
            if (Object.create) {
                return Object.create(o);
            } else {
                F.prototype = o;
                return new F();
            }
            function F(){}
        },
        queryUrl: function(str){
            var url = decodeURI(window.location.href);
            var rs = new RegExp("(^|)" + str + "=([^/&#]*)(#|&|$)","gi").exec(url);
            if (rs) {return rs[2];}
            return '';
        },
        /**
         * 去除字符串前后的空格
         **/
        trim: function(text) {
            if (text == null) return '';
            var trim = String.prototype.trim;
            var rtrim = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g;       //trim BOM and nbsp, ie9-
            return (trim) ? trim.call(text) : (text + '').replace(rtrim, '');
        },
        /**
         * 获取对象类型
         **/
        type: function(obj) {
            var name = ['Boolean', 'Number', 'String', 'Function', 'Array', 'Date', 'RegExp', 'Object'],
                len = name.length,
                i = 0;
            if (this.isEmptyObject(this.class2type)) {
                for (; i < len; i++) {
                    this.class2type['[object ' + name[i] + ']'] = name[i].toLowerCase();
                }
            }
            return obj == null ? String(obj) : this.class2type[toString.call(obj)] || 'object';
        },
        class2type: {},
        /**
         * 将字符串中的特殊字符转为实体编码或实体字符
         **/
        getCharEntity: function(str) {
            return str.replace(/['"&\\/<>]/g, function(match) {
                return '&#x' + match.charCodeAt().toString(16) + ';'
            });
        },
        /**
         * 节流
         **/
        throttle: function(handler, wait) {
            var timer = null;
            return function(){
                var self = this,
                    args = arguments;
                if (timer) {return;} 
                timer = setTimeout(function(){
                    // clearTimeout(timer);
                    timer = null;
                    handler.apply(self, args);
                }, wait);
            }
        },
        /**
         * 防抖
         **/
        debounce: function(handler, delay){
            var timer = null;
            return function(){
                var self = this,
                    args = arguments;
                clearTimeout(timer);
                timer = setTimeout(function(){
                    handler.apply(self, args);
                }, delay);
            }
        },
        /**
         * 补零（补零原则：补零后，数值不变）
         * 比如：10 ---> 10.00, 1 ---> 01, 10 -X-> 1000, 0.1 -X-> 0.01
         * 参数：
         * n - 要补零的数字
         * digit - number。最大补零位数。默认：2
         * pos - number。补零位置。 值：1（默认）||-1。在右侧或左侧补零。
         * 返回值：String
         **/
        zeroFill: function(n, digit, pos){
            n = parseFloat(n);
            if (n == 0 || pos == -1 && n < 0) { return n + '';}
            var a = (n + '').split('.');
            if (a[1] && pos === -1) {return n + '';}
            if (!a[1]) {a.push('0');}
            digit = san.tools.type(digit) === 'number' && digit ? digit : 2;
            pos = san.tools.type(pos) === 'number' && pos < 0 ? -1 : 1;
            var i, len = a[0].length - 1, z = '';
            if (pos == -1 && len >= digit) { return n + ''; }
            for (i = 0; i < (digit - len); i++){
                z += '0';
            }
            if (pos == -1){
                return z + n;
            }
            if (pos == 1){
                a[1] = (a[1] + z).substring(0, Math.max(digit, a[1].length));
                return a[0] + '.' + a[1];
            }
        }
    }

    san.tools.getJsonData = function(option){
        var opt = {
            url: '',
            type: 'POST',
            dataType: 'json',
            cache: false,
            timestamp: true,
            data: null,
            onBefore: function(){}, 
            onDone: function(){},
            onFail: function(){},
            onAlways: function(){}
        }

        if (option && san.tools.type(option) === 'object') {
            opt = $.extend({}, opt, option);
        }

        $.ajax({
            url: opt.timestamp ? san.tools.urlTimestamp(opt.url) : opt.url,
            type: opt.type,
            dataType: opt.dataType,
            cache: opt.cache,
            data: opt.data,
            beforeSend: function(){
                opt.onBefore();
            }
        }).done(function(data, textStatus, jqXHR){
            opt.onDone(data, textStatus, jqXHR);
        }).fail(function(data, textStatus, jqXHR){
            opt.onFail(data, textStatus, jqXHR);
        }).always(function(data, textStatus, jqXHR){
            opt.onAlways(data, textStatus, jqXHR);
        });
    }

    /**
     * 浏览器相关
     */
    san.browser = {
        /**
         * 获取IE版本（用户代理字符串）
         * 返回值：IE版本号。非IE返回-1
         **/
        ieAgent: function(){
            var naviVersion = navigator.userAgent.toLowerCase();
            var msie = naviVersion.indexOf('msie'),
                trident = naviVersion.indexOf('trident'),
                ver = -1;
            if (~trident && naviVersion.match(/trident\D*[4-7]/)[0].replace(/\D/g, '') == 7) {
                return 11;
            }
            if (~msie) {
                ver = naviVersion.match(/(msie)\D*\d+/)[0].replace(/\D/g, '');
                var hasQuerySelector = 'querySelector' in document,
                    computedStyle = window.getComputedStyle,
                    hasPushState = 'pushState' in window.history;
                if (hasPushState) { return 10; }      // 10+
                if (computedStyle && !hasPushState) { return 9; }
                if (hasQuerySelector && !computedStyle) { return 8; }
                if (!hasQuerySelector) { return ver > 6 ? 7 : ver; }   // 7-
            }
            return -1;
        },
        /**
        * 获取浏览器类型及版本（用户代理字符串）
        **/
        client: function() {
            var b = {
                'name': '',
                'version': ''
            }
            var naviVersion = navigator.userAgent.toLowerCase();
            // ie
            if (~naviVersion.indexOf('msie') || ~naviVersion.indexOf('trident')) {
                b.name = 'ie';
                b.version = san.browser.ieAgent();
                return b;
            }
            // edge
            var regEdge = /(edge)\D+(\d[\d.]*)+(.\d[\d.]*)*/i;
            if (~naviVersion.indexOf('edge')) {
                b.name = 'edge';
                if (regEdge.test(naviVersion)) {
                    b.version = RegExp.$2;
                }
                return b;
            }
            // safari
            var regSafari = /(version)\D+(\d[\d.]*)+(.\d[\d.]*)*/i;
            if (~naviVersion.indexOf('applewebkit') && ~naviVersion.indexOf('version') && ~naviVersion.indexOf('safari')) {
                b.name = 'safari';
                if (regSafari.test(naviVersion)) {
                    b.version = RegExp.$2;
                }
                return b;
            }
            // chrome, firefox...
            var regb = /(chrome|CriOS|firefox|opera)\D+(\d[\d.]*)+(.\d[\d.]*)*/i;
            if (regb.test(naviVersion)) {
                b.name = (RegExp.$1).toLowerCase();
                if (b.name == 'crios') {
                    b.name = 'chrome';
                }
                b.version = RegExp.$2;
            }
            // if (b.name) {
            //     b.name = b.name.substring(0,1).toUpperCase() + b.name.substring(1);
            // }
            return b;
        },
        /**
         * 获取滚动条尺寸
         **/
        scrollDetector: function(){
            $('body').append('<div id="scroll-detector" style="position:absolute;top:-1000px;left:-1000px;overflow-y:auto;overflow-x:hidden;width:50px;height:50px;overflow-y:auto;overflow-x:hidden;opacity:0;background-color:#ccc;"><div class="sd-inner" style="height:200px;background-color:#fff;">scroll-detector</div></div>');
            var sdtr = document.getElementById('scroll-detector'),
                v = sdtr.offsetWidth - sdtr.clientWidth;
            sdtr.parentNode.removeChild(sdtr);
            return (v > 0) ? v : 0;
        }
    }

    /**
     * 获取视口和文档大小
     */
    san.view = {
        /**
         * 获取屏幕物理像素与dip的比例
         **/
        dpr: function() {
            var w = window, ws = window.screen, sr = w.devicePixelRatio;
            if (sr) { return sr; }
            if (ws.deviceXDPI && ws.logicalXDPI) { return ws.deviceXDPI / ws.logicalXDPI; }
            return -1;
        },
        /**
         * 视口尺寸
         **/
        viewport: function() {
            return {
                'width': window.innerWidth || DOC.documentElement.clientWidth,
                'height': window.innerHeight || DOC.documentElement.clientHeight
            }
        },
        /**
         * 视域尺寸
         **/
        viewArea: function() {
            var docElem = DOC.documentElement,
                docBody = DOC.body;
            return {
                'width': docElem.clientWidth || docBody.clientWidth,
                'height': docElem.clientHeight || docBody.clientHeight
            }
        },
        /**
         * 页面文档尺寸
         **/
        document: function() {
            var docElem = DOC.documentElement,
                docBody = DOC.body;
            return {
                'width': Math.max(docBody.scrollWidth, docBody.clientWidth, docElem.offsetWidth),
                'height': Math.max(docBody.scrollHeight, docBody.clientHeight, docElem.offsetHeight)
            }
        },
        /**
         * 屏幕尺寸
         **/
        screen: function() {
            var s = window.screen;
            return {
                'width': s.availWidth,
                'height': s.availHeight,
                'fullWidth': s.width,
                'fullHeight': s.height
            }
        },
        /**
         * 元素到文档顶部/左侧的距离
         **/
        offset: function(elem) {
            var win, doc, docElem,
                box = {top: 0, left: 0};
            
            if (elem instanceof jQuery) {
                elem = elem[0];
            }
            
            doc = elem && elem.ownerDocument;
            if (!doc) {
                return;
            }
            docElem = doc.documentElement;

            if (!$.contains(docElem, elem)) {
                return box;
            }

            box = elem.getBoundingClientRect();

            win = getWindow(doc);
            
            return {
                top:  box.top  + (win.pageYOffset || docElem.scrollTop  || doc.body.scrollTop)  - (docElem.clientTop  || doc.body.clientTop  || 0),
                left: box.left + (win.pageXOffset || docElem.scrollLeft || doc.body.scrollLeft) - (docElem.clientLeft || doc.body.clientLeft || 0)
            };

            function getWindow(elem) {
                return san.tools.isWindow(elem) ? elem :
                    elem.nodeType === 9 ? elem.defaultView || elem.parentWindow : false;
            }
        },
        /**
         * 滚动条滚动距离 
         **/
        scroll: function() {
            var docElem = DOC.documentElement,
                docBody = DOC.body;
            return {
                'top':  window.pageYOffset || docElem.scrollTop  || docBody.scrollTo,
                'left': window.pageXOffset || docElem.scrollLeft || docBody.scrollLeft
            }
        },
        /**
         * 元素在可视区域中的坐标信息以及其占用面积尺寸
         **/
        rect: function(elem) {
            var rect;
            if (elem instanceof jQuery) {
                elem = elem[0];
            }
            rect = elem.getBoundingClientRect();
            return {
                'top': rect.top,
                'left': rect.left,
                'bottom': rect.bottom,
                'right':  rect.right,
                'width': rect.width || rect.right - rect.left,
                'height': rect.height || rect.bottom - rect.top
            }
        }
    }

    san.listener = {
        mediaQuery: function(){
            var n;
            for (n in MEDIA_LISTENER_GROUP) {
                if (!san.tools.contain(MEDIA_LISTENER_GROUP[n])) {
                    delete MEDIA_LISTENER_GROUP[n];
                    continue;
                }
                if (/san-datasheet-/i.test(n) && n != MEDIA_LISTENER_GROUP[n].getAttribute('data-datasheet') || /san-pagination-/i.test(n) && n != MEDIA_LISTENER_GROUP[n].getAttribute('san-pagination') || /san-expander-/i.test(n) && n != MEDIA_LISTENER_GROUP[n].getAttribute('data-expander')) {
                    delete MEDIA_LISTENER_GROUP[n];
                    continue;
                }
                if (!(/(side-menu-|san-tabs-)/i.test(n))){
                    if (!san.view.rect(MEDIA_LISTENER_GROUP[n]).width) { continue; }
                }
                $(MEDIA_LISTENER_GROUP[n]).trigger(MEDIA_LISTENER);
            }
        },
        resizeQuery: function(){
            var n;
            for (n in RESIZE_LISTENER_GROUP) {
                if (!san.tools.contain(RESIZE_LISTENER_GROUP[n])) {
                    delete RESIZE_LISTENER_GROUP[n];
                    continue;
                }
                if (!san.view.rect(RESIZE_LISTENER_GROUP[n]).width) { continue; }
                $(RESIZE_LISTENER_GROUP[n]).trigger(RESIZE_LISTENER);
            }
        },
        scrollQuery: function(){
            var n;
            for (n in SCROLL_LISTENER_GROUP) {
                if (!san.tools.contain(SCROLL_LISTENER_GROUP[n]) || n != SCROLL_LISTENER_GROUP[n].getAttribute('data-datasheet')) {
                    $('#suspend-bar-' + n).remove();
                    delete SCROLL_LISTENER_GROUP[n];
                    continue;
                }
                if (!san.view.rect(SCROLL_LISTENER_GROUP[n]).width) { continue; }
                $(SCROLL_LISTENER_GROUP[n]).trigger('suspendScroll');
            }
        },
        duplicated: function(target, group, attrName){
            var n;
            for (n in group) {
                if (target == group[n]) {
                    delete group[n];
                    $('#suspend-bar-' + n).remove();
                }
            }
        }
    }

    san.widget = {init:function(b,a,c){this.methods=a;this.$elem=b;return this.setup.apply(this,c)},setup:function(){var a=this.methods,b=this.$elem,c=arguments[0];if(typeof c==="object"||!c){return a.init.apply(b,arguments)}if(!a[c]){return}return a[c].apply(b,Array.prototype.slice.call(arguments,1))}};
    san.widget.data = san.tools.objectCreate(null);

    window.san = san;

})(jQuery);



function initStandby(fn, interval) {
    interval = interval && san.tools.type(interval) === 'number' ? interval : 10;
    var waitingTimer = setInterval(function(){
        if (GLOBE_INIT) {
            clearInterval(waitingTimer);
            fn();
        }
    }, interval);
}



/**
 * sanMainMenu
 * 主菜单下拉菜单
 * @author: zhxming
 * 自定义属性：
 * data-chanel：存储chanel名称。自动获取菜单项文本生成。该属性一般用于设置菜单状态。
 */
;(function($){
    'use strict';

    var config = {
        data: null,
        //菜单项CLASS
        item: 'menu-item',
        //激活的菜单项CLASS
        active: 'active',
        // 当前菜单项CLASS
        current: 'current',
        //下拉菜单容器CLASS
        dropPanel: 'drop-menu',
        dropItem: 'drop-item',
        level1: 'lv-1',
        level2: 'lv-2',
        level3: 'lv-3',
        // 主菜单入口控制柄id
        handle: 'main-menu-handle',
        // 被入口控制柄激活的主菜单，CLASS
        handleActive: 'handle-active',
        handingEvent: DEFAULT_EVENT,
        namespace: 'sanMainMenu'
    };

    var $mainpage, $menu, $clone,
        isMoving = false;

    var methods = {
        init: function(option){
            return this.each(function(){
                var $this = $(this),
                    opt = $.extend({}, config, option),
                    namespace = opt.namespace,
                    handingEvent = opt.handingEvent,
                    item = opt.item,
                    active = opt.active,
                    current = opt.current;

                $this.data('options', opt);

                $mainpage = $(TOP_DIV),
                $menu = $('#main-page-menu');
                $clone = $('#main-menu-2');

                //methods.build.call($this);

                $this.addClass('resolved');
                
                $this.find('.' + item).each(function(){
                    var $item = $(this);
                    if ($item.find('.' + opt.dropPanel).length) {
                        $item.addClass('has-drop');
                    }
                });
                
                var inTimer = null, y1, y2;
                
                // 鼠标移入移出事件
                $this.on('mouseenter.' + namespace, '.' + item, function(){
                    if (V_VW < MEDIA_RULE.M) {return;}
                    methods.dropShow.call($this, $(this));
                }).on('mouseleave.' + namespace, '.' + item, function(){
                    if (V_VW < MEDIA_RULE.M) {return;}
                    methods.dropHide.call($this, $(this));
                });

                $(DOC).on(handingEvent + '.sanMainMenu', '#main-menu-handle', function() {
                    // if (V_VW >= MEDIA_RULE.M) {return;}
                    if ($this.hasClass(opt.handleActive)) {
                        methods.menuHide.call($this);
                    } else {
                        methods.menuShow.call($this);
                    }
                });

                $(window).on('resize.' + namespace, san.tools.throttle(function(){
                    clearInterval(inTimer);
                    inTimer = setInterval(function(){
                        if (GLOBE_INIT) {
                            clearInterval(inTimer);
                            if (RESIZE_IGNORE) {return;}
                            if (methods.handleActive.call($this) && $this.hasClass(opt.handleActive)) {
                                methods.menuHide.call($this);
                            }
                        }
                    }, 10);
                }, 200));

                $this.on(handingEvent + '.' + namespace, 'a', function(e){
                    if (isMoving) { return; }
                    
                    var $a = $(this),
                        $li = null,
                        url,
                        $item = null,
                        exclude = false;

                    if ($a.hasClass('exclude')) {
                        exclude = true; 
                    } else {
                        e.preventDefault();
                    }

                    $li = $a.parent();
                    url = $a.attr('data-url');
                    $item = $li.closest('.' + item);

                    if (V_VW >= MEDIA_RULE.M) {
                        if ($li.hasClass(item) && $li.find('.' + opt.dropPanel).length) {
                            if (!$item.hasClass(active)){
                                methods.dropHide.call($this, $item.siblings('.' + item));
                                methods.dropShow.call($this, $item);
                            }else{
                                methods.dropHide.call($this, $item);
                            }
                            if (!exclude) {
                                jumpto($a[0].href);
                            }
                            return;
                        }

                        if ($li.hasClass(current)) {
                            return;
                        }

                        setTimeout(function(){
                            methods.dropHide.call($this, $item);
                        }, 20);

                        if (!exclude) {
                            jumpto($a[0].href);
                        }
                        return;
                    }

                    e.stopPropagation();

                    if ($li.hasClass(item)) {
                        if ($li.hasClass('has-drop')) {
                            if (!$li.hasClass(active)){
                                $li.siblings('.' + item).each(function(){
                                    methods.dropHide.call($this, $(this));
                                });
                                methods.dropShow.call($this, $item);
                            } else {
                                methods.dropHide.call($this, $item);
                            }
                            methods.clearDropItemActive.call($this);
                        } else {
                            if (!exclude) {
                                methods.menuHide.call($this);
                                jumpto($a[0].href);
                            }
                        }
                        return;
                    }

                    if ($a.hasClass(opt.level2)) {
                        var $dorpItem = $li.closest('.' + opt.dropItem);
                        if ($dorpItem.hasClass('has-drop')) {
                            if (!$dorpItem.hasClass(active)) {
                                methods.clearDropItemActive.call($this);
                                $dorpItem.addClass(active);
                            } else {
                                // $dorpItem.addClass(active);
                                methods.dropHide.call($this, $dorpItem);
                            }
                        } else if (!$li.hasClass(current)) {
                            setTimeout(function(){
                                methods.menuHide.call($this);
                            }, 10);
                            if (!exclude) {
                                jumpto($a[0].href);
                            }
                        }
                        return;
                    }
                    
                    if ($li.hasClass(current)) {
                        return;
                    }

                    if ($a.hasClass(opt.level3)) {
                        if (!exclude) {
                            methods.menuHide.call($this);
                            jumpto($a[0].href);
                        }
                        return;
                    }

                });

                function jumpto(url) {
                    setTimeout(function(){
                        window.location.href = url;
                    }, 200);
                }

                $clone.on(handingEvent + '.' + namespace, 'a', function(e){
                    if (isMoving) { return; }
                    e.preventDefault();
                    var $a = $(this),
                        $li = $a.parent();
                    $this.find('[data-mid="' + $li.attr('data-mid') + '"]').children().trigger(handingEvent);
                });

                if (handingEvent == 'touchend') {
                    var $container = $this.parent();
                    $container.off('touchstart touchmove');
                    $container.on('touchstart.' + namespace, function(e) {
                        isMoving = false;
                        y1 = e.originalEvent.touches[0].pageY;
                    });
                    $container.on('touchmove.' + namespace, function(e) {
                        y2 = e.originalEvent.touches[0].pageY;
                        if (Math.abs(y2 - y1) > 2){
                            isMoving = true;
                        }
                    });    
                }
            });
        },
        /**
         * 生成主菜单
         */
        build: function(){
            return this.each(function() {
                var $this = $(this),
                    opt = $this.data('options'),
                    records = opt.data.data.nodes;
                var route = '', route2 = '';

                $this.sanTemplate({
                    data: opt.data.data
                });

                $clone.sanTemplate({
                    data: opt.data.data
                });

                var i = -1;
                $.each(records, function(n, v) {
                    if (route = v.route.path) {
                        ROUTE_MAP[route] = {
                            'id': v.mid,
                            'name': v.name,
                            'marker': v.marker,
                            'url': v.url,
                            'topIndex': ++i
                        }
                    }
                    if (v.nodes) {
                        route2 = route;
                        buildRouteMap(v.nodes);
                        route2 = '';
                    }
                });
                
                $.each(_DATA_CHANNEL, function(n, v){
                    ROUTE_MAP[n] = v;
                });

                function buildRouteMap(data) {
                    $.each(data, function(n, v) {
                        if (route = v.route.path) {
                            if (route2) {
                                route = route2 + '/' + route;
                            }
                            ROUTE_MAP[route] = {
                                'id': v.mid,
                                'name': v.name,
                                'marker': v.marker,
                                'url': v.url,
                                'topIndex': i
                            }
                        }
                        if (v.nodes) {
                            buildRouteMap(v.nodes);
                        }
                    });
                }
            });
        },
        /**
         * 主菜单入口控制柄是否处于激活状态
         */
        handleActive: function(){
            var $this = $(this),
                opt = $this.data('options');
            var handle = document.getElementById(opt.handle);
            var styleList;
            if ('defaultView' in document) {
                styleList = document.defaultView.getComputedStyle(handle, null);
            } else {
                styleList = handle.currentStyle;
            }
            return styleList.display == 'none' ? false : true;
        },
        /**
         * 显示主菜单
         */
        menuShow: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    handleActive = opt.handleActive;
                $this.addClass(handleActive);
                
                var n;
                for (n in SCROLL_LISTENER_GROUP) {
                    $('#suspend-bar-' + n).css('z-index', '-1');
                }

                $mainpage.css('top', '-' + san.view.scroll().top + 'px').addClass('masked');
                $menu.addClass(handleActive);
            });
        },
        /**
         * 隐藏主菜单
         */
        menuHide: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    handleActive = opt.handleActive,
                    top = Math.abs(parseInt($mainpage.css('top')));
                $this.removeClass(handleActive);
                $mainpage.css('top', '').removeClass('masked');
                $('html, body').scrollTop(top);
                $menu.removeClass(handleActive);

                methods.clearActive.call($this);

                var n;
                for (n in SCROLL_LISTENER_GROUP) {
                    $('#suspend-bar-' + n).css('z-index', '');
                }
            });
        },
        /**
         * 显示下拉菜单
         */
        dropShow: function($obj){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $dropPanel = $obj.find('.' + opt.dropPanel),
                    active = opt.active;
                
                $obj.addClass(active);
                $clone.find('[data-mid="' + $obj.closest('.' + opt.item).attr('data-mid') + '"]').addClass(active);

                if (V_VW < MEDIA_RULE.M) {return;}

                var th = $('#main-page-head').outerHeight() + $menu.outerHeight(),
                    bh = $('#main-page-body').outerHeight(),
                    dh = $dropPanel.outerHeight();
                if (bh < dh) {
                    $mainpage.css({'min-height': th + dh + 20 + 'px'});
                }
            });
        },
        /**
         * 隐藏下拉菜单
         */
        dropHide: function($obj){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    active = opt.active;

                $obj.removeClass(active);
                $clone.find('[data-mid="' + $obj.closest('.' + opt.item).attr('data-mid') + '"]').removeClass(active);
                $mainpage.css({'min-height': 'auto'});
            });
        },
        /**
         * 设置当前状态
         * index: data-mid
         */
        setCurrent: function(index, fn){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $li = null,
                    $parent = null,
                    active = opt.active,
                    current = opt.current;

                if (san.tools.type(index) === 'function') {
                    fn = index;
                    index = null;
                }

                if (index === false) {
                    $this.find('.' + current).removeClass(current);
                    return;
                }
                $li = !index ? $this.find('[data-index="0"]:eq(0)') : $this.find('[data-mid="' + index +'"]');
                index = $li.attr('data-mid');
                if (!$li.length) {
                    $li = $this.find('[data-channel="' + index +'"]').parent();
                    index = $li.attr('data-mid');
                }
                $parent = $li.parent();

                if ($li.hasClass(current)) {
                    return;
                }

                $this.find('.' + active).removeClass(active);
                $this.find('.' + current).removeClass(current);
                $li.addClass(current);

                $clone.find('.' + current).removeClass(current);
                $clone.find('.' + active).removeClass(active);
                $clone.find('[data-mid="' + index +'"]').addClass(current);

                var $dropItem = null;
                if (!$li.hasClass(opt.item)) {
                    $li.closest('.' + opt.item).addClass(current);
                    $clone.find('[data-mid="' + $li.closest('.' + opt.item).attr('data-mid') +'"]').addClass(current).siblings().removeClass(current)
                    $dropItem = $li.closest('.' + opt.dropItem);
                    // if ($li.children('a').hasClass(opt.level3)) {
                    //     $dropItem.addClass(current);
                    // }
                    $dropItem.addClass(current).addClass(active);
                    if ($dropItem.hasClass('has-drop')) {
                        // 二级菜单能点击跳转的特殊情况
                        if ($li.children('a').hasClass(opt.level2)) {
                            methods.menuHide.call($this);
                        }
                    }
                }

                //methods.setBackground.call($this, index);

                if (fn && typeof fn == 'function'){
                    fn.call($this);
                }
            });
        },
        /**
         * 设置子页面背景图片
         * index: data-mid
         * url：图片路径。url存在则优先设置
         */
        setBackground: function(index, url) {
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $li,
                    i,
                    bannerUrl = (url && typeof url === 'string') ? url : null;
                
                if (!bannerUrl) {
                    $li = !index ? $this.find('[data-index="0"]:eq(0)') : $this.find('[data-mid="' + index +'"]');
                    i = $li.closest('.' + opt.item).attr('data-index');
                    bannerUrl = opt.data.data.nodes[i].banner;
                }
                bannerUrl = bannerUrl ? 'url(' + bannerUrl + ')' : 'none';
                $('#main-page-body').children('.main-page-body-inner').css('background-image', bannerUrl);
            });
        },
        /**
         * 清除active状态
         */
        clearActive: function($obj) {
            return this.each(function(){
                var $this = $(this),
                opt = $this.data('options'),
                active = opt.active;

                if ($obj) {
                    $obj.removeClass(active);
                    methods.clearDropItemActive.call($this, $obj);
                } else {
                    $this.find('.' + opt.item).removeClass(active);
                    $clone.find('.' + active).removeClass(active);
                    methods.clearDropItemActive.call($this);
                }
            });
        },
        /**
         * 清除active状态
         */
        clearDropItemActive: function($obj) {
            return this.each(function(){
                var $this = $(this),
                opt = $this.data('options'),
                active = opt.active,
                dropItem = opt.dropItem,
                findSelector = '.' + dropItem + '.' + active + ':not(.' + opt.current + ')';

                if ($obj) {
                    // $obj.closest('.' + opt.item).find(findSelector).removeClass(active);
                    if ($obj.hasClass(dropItem)) {
                        $obj.removeClass(active);
                    } else if ($obj.hasClass(opt.item)) {
                        $obj.find(findSelector).removeClass(active);
                    } else {
                        $obj.closest('.' + opt.item).find(findSelector).removeClass(active);
                    }
                } else {
                    $this.find(findSelector).removeClass(active);
                }
            });
        },
        /**
         * htmlDEMOJumpto()仅用于本htmlDEMO内的菜单访问功能，实际开发中页面之间并非采用此种方式跳转。
         * 点击菜单项跳转页面
         */
        htmlDEMOPlus: function(setDefault){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    event = opt.handingEvent + '.htmlDEMO';

                $this.on(event, 'a', function(e){
                    e.stopPropagation();
                    if (isMoving) { return; }
                    if ($(this).hasClass('exclude')) {return; }
                    var $a = $(this),
                        $li = $a.parent(),
                        mid = $li.attr('data-mid'),
                        url = $a.attr('data-url'),
                        index = $a.attr('data-chanel'),
                        route = $a.attr('data-route'),
                        $item = $li.closest('.' + opt.item);
                    //href控制权
                    var href = $a.attr('href');
                    if (href && href.indexOf('javascript') == -1) return;
                    e.preventDefault();
                    //一级菜单时
                    // if ($a.hasClass(opt.level1) && $a.nextAll('.' + opt.dropPanel).length != 0) return;
                    // if (!url) return;

                    if ($li.hasClass(opt.item) && $li.find('.' + opt.dropPanel).length) {return;}
                    if ($li.hasClass(opt.current)) {return;}
                    
                    if (url) {
                        MEDIA_LISTENER_GROUP = san.tools.objectCreate(null);
                        RESIZE_LISTENER_GROUP = san.tools.objectCreate(null);

                        $('body').children('.san-datasheet-suspend-bar').remove();
                        SCROLL_LISTENER_GROUP = san.tools.objectCreate(null);

                        $(document).sanRouter('add', route);
                        return;
                    }

                    // 需登录和手机验证的频道
                    if (~('1-4|1-5|1-6'.indexOf($li.attr('data-mid')))) {
                        popupConfirm(JURL + ROUTE['signin'] + '/validate-phone.html');
                    }
                });

                // 默认选中项
                if (setDefault !== false) {
                    var currentHash = window.location.hash.toLocaleLowerCase().substring(1);
                    if (regHash.test(currentHash)) {
                        $(window).trigger('hashchange.sanRouter');
                    } else {
                        // $this.find('[data-url]:eq(0)').trigger(event); 
                        $this.find('[data-channel="首页"]:eq(0)').trigger(event); 
                    }
                }
                
                // 添加标记
                $this.find('[data-url]:not(.' + opt.level1 + ')').each(function(){
                    var $item = $(this),
                        url = $item.attr('data-url'),
                        href = $item.attr('href');
                    if (url) {
                        $item.append('<sup>*</sup>');
                    } else if (!~href.indexOf('void(0)')) {
                        $item.append('<sup>+</sup>');
                    }
                });
            });
        }
    };

    $.fn.sanMainMenu = function(){
        var mainMenu = san.tools.objectCreate(san.widget);
        return mainMenu.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanSideMenu
 * 侧边下拉菜单
 * @author: zhxming
 * 约束：
 * 严格遵循HTML结构，参照html模板
 * 自定义属性：
 * data-channel：存储channel名称。值与菜单项指向的子页面中的rel-channel-id相对应，用于反向设置菜单状态。
 *               因确保该值的唯一性，默认自动获取菜单名文本生成，如有重名菜单名，需手动设置菜单项的data-channel值。
 */
;(function($){
    'use strict';

    var config = {
        data: '',
        //CLASS，侧边菜单标题。内容即主菜单的一级菜单项
        menuTitle: 'side-menu-title',
        //CLASS，菜单项容器，必须是<ul>或<ol>
        menuList: 'side-menu-list',
        //CLASS，下拉菜单容器，必须是<ul>或<ol>
        menuDropList: 'side-menu-drop-list',
        // CLASS，菜单项
        menulevel: 'lv',
        // CLASS，一级菜单项，在menuTitle上做为侧边菜单标题
        level1: 'lv-1',      
        // CLASS，二级菜单项，位于<a>上
        level2: 'lv-2',
        // CLASS，三级菜单项（在menuDropList中），位于<a>上
        level3: 'lv-3',
        //CLASS，当前的菜单项，设置在<a>上
        current: 'current',
        //菜单状态完成时执行。index菜单索引值（data-channel）
        onDone: function(index){}
    };

    var methods = {
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this),
                    sideMenuId;

                sideMenuId = san.tools.uuid('side-menu-');
                $this.attr('data-sidemenu', sideMenuId);
                opt.sideMenuId = sideMenuId;

                $this.data('options', opt);

                $this.attr('data-listener', 'media');
                MEDIA_LISTENER_GROUP[sideMenuId] = $this[0];

                //methods.build.call($this);

                $this.on(MEDIA_LISTENER + '.sanSideMenu', function(e, enforce) {
                    initStandby(function(){
                        $this.sanSideMenu('dropSetup', $this.find('.' + opt.current + '.has-drop').children('.' + opt.menuDropList));
                    });
                });
            });
        },
        build: function(){
            return this.each(function() {
                var $this = $(this),
                    opt = $this.data('options');
                
                $this.sanTemplate({
                    data: opt.data
                });
            });
        },
        dropSetup: function($drop){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    h = 0;
                $drop.find('li').each(function(){
                    h += $(this).outerHeight(true);
                });
                $drop.css('height', h + 'px');
            });
        },
        /**
         * 设置当前状态
         * index: data-channel
         */
        setCurrent: function(index, fn){
            return this.each(function(){
                var $this = $(this),
                    opt = opt = $this.data('options'),
                    menuDropList = opt.menuDropList,
                    current = opt.current;
                
                //index = index.toLowerCase();

                var $a = $this.find('a[data-channel="' + index +'"]'),
                    $li = $a.parent(),
                    $title = $this.find('.' + opt.menuTitle),
                    $level1 = null, $level2 = null, $level3 = null,
                    $lv2 = null;

                // if ($li.hasClass(current)) {return;}

                if (window.localStorage) {
                    STORAGE_CHANNEL = JSON.parse(localStorage.getItem('channel'));
                }

                // 一级菜单项level1作为侧边菜单的标题，和level2一样常显，level3隐藏
                if ($a.hasClass(opt.level1)){
                    $level1 = $a;
                }else if ($a.hasClass(opt.level2)){
                    $level2 = $a; 
                }else{
                    $level3 = $a;
                    $level2 = $a.closest('.' + menuDropList).siblings('.' + opt.level2);
                }

                // 作为标题的level1可点击的特殊情况
                if (!!$level1){
                    $this.find('.' + current).removeClass(current);
                    $this.find('.' + menuDropList).addClass('hide');
                    if (fn && typeof fn == 'function'){
                        fn.call($this);
                    }
                    return;
                }  
                
                $lv2 = $level2.parent();
                if ($lv2.hasClass('has-drop')) {
                    if (san.tools.type(STORAGE_CHANNEL) != 'object' || (san.tools.type(STORAGE_CHANNEL) == 'object' && STORAGE_CHANNEL.level2.mid != $lv2.attr('data-mid'))) {
                        $level2.next().addClass('animate');
                    }
                    methods.dropSetup.call($this, $level2.next());
                }

                if (!!$level3){
                    $level3.parent().addClass(current).siblings().removeClass(current);
                    $level2.parent().addClass(current).siblings().removeClass(current).find('li').removeClass(current);
                }else{
                    $lv2.addClass(current).siblings().removeClass(current).find('li').removeClass(current);
                    // level2本身带有data-url跳转，并且有下级菜单的特殊情况
                    if ($a.hasClass(opt.level2) && $lv2.hasClass('has-drop')){
                        $lv2.find('li').removeClass(current);
                    }
                    // $lv2 = null;
                }

                $level2.nextAll('.' + menuDropList).removeClass('hide');
                $lv2.siblings().find('.' + menuDropList).addClass('hide');
                setTimeout(function(){
                    $level2.next().removeClass('animate');
                }, 200);
                
                $title.find('.title-s').attr({
                    'data-mid': $li.attr('data-mid'),
                    'data-channel': $a.attr('data-channel')
                }).text($a.html().replace(/<sup>[\d\D]+<\/sup>/gi, ''));

                var _channel = san.tools.objectCreate(null);
                _channel.level1 = san.tools.objectCreate(null);
                _channel.level2 = san.tools.objectCreate(null);
                _channel.level3 = san.tools.objectCreate(null);
                $.each([$level1, $level2, $level3], function(n, v){
                    setChannelStorage(_channel, v, 'level' + (n + 1));
                });
                if (window.localStorage) {
                    localStorage.setItem('channel', JSON.stringify(_channel));
                }

                if ($('#main-menu').find('[data-mid="' + $li.attr('data-mid') + '"]').length) {
                    $('#main-menu').sanMainMenu('setCurrent', $li.attr('data-mid'));
                } else {
                    //methods.setBackground.call($this, $li.attr('data-topmid'));
                }

                if (fn && typeof fn == 'function'){
                    fn.call($this);
                }

                function setChannelStorage(obj, $target, level){
                    if (!!$target) {
                        obj[level].mid = $target.parent().attr('data-mid');
                        obj[level].channel = $target.attr('data-channel')
                        obj[level].url = $target.attr('data-url') || '';
                    } else {
                        obj[level].mid = '';
                        obj[level].channel = '';
                        obj[level].url = '';
                    }
                }
            });
        },
        /**
         * 设置子页面背景图片
         * index: data-mid
         * url：图片路径。url存在则优先设置
         */
        setBackground: function(index, url) {
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $li,
                    i,
                    bannerUrl = (url && typeof url === 'string') ? url : null;
                
                if (!bannerUrl) {
                    bannerUrl = DATA_CHANNEL.data.nodes[index].banner;
                }
                bannerUrl = bannerUrl ? 'url(' + bannerUrl + ')' : 'none';
                $('#main-page-body').children('.main-page-body-inner').css('background-image', bannerUrl);
            });
        },
        /**
         * htmlDEMO专用补丁
         * 注意：
         * htmlDEMOPlus()仅用于本htmlDEMO内使用，是为了即避免代码重复开发又能使用菜单访问各个页面而开发的；
         * 实际开发中页面之间并非采用此种方式跳转。
         * 当data-url和href同时有有效值时，href无效，已data-url为准
         */
        htmlDEMOPlus: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');

                //点击事件
                $this.off(DEFAULT_EVENT + '.htmlDEMO', '.' + opt.menulevel);
                $this.on(DEFAULT_EVENT + '.htmlDEMO', '.' + opt.menulevel, function(e){
                    var $a = $(this),
                        $li = $a.parent(),
                        $drop = $li.find('.' + opt.menuDropList);
                    // if ($a.hasClass(opt.level3) && $li.hasClass(opt.current)) {return false;}

                    // level2本身带有data-url跳转，并且有下级菜单的特殊情况
                    // if ($a.hasClass(opt.level2) && $a.attr('data-url') && $drop.length && !$drop.hasClass('hide') && !$drop.find('.' + opt.current).length){
                    //     return;
                    // }

                    var url = $a.attr('data-url');

                    // 如果有data-url时阻止href行为
                    if (url){e.preventDefault();}

                    //当前项无url将寻找有url的下级菜单项
                    if (!url && $drop.length){
                        var ig = null;
                        $drop.find('.' + opt.level3).each(function(){
                            var _$a = $(this),
                                _url = _$a.attr('data-url');
                            if (!sanIgnoreHref(_$a.attr('href'))){
                                ig = _$a[0];
                            }
                            if (_url){
                                $a = _$a;
                                url = _url;
                                ig = null;
                                return false;
                            }
                        });
                        // 如果下级菜单项只有一个并且仅有href有效值时
                        if (ig){ig.click();}
                    }

                    // 阻止html操作权或操作权交由html（href）
                    if (url){
                        MEDIA_LISTENER_GROUP = san.tools.objectCreate(null);
                        MEDIA_LISTENER_GROUP[opt.sideMenuId] = $this[0];
                        RESIZE_LISTENER_GROUP = san.tools.objectCreate(null);
                        $('body').children('.san-datasheet-suspend-bar').remove();
                        SCROLL_LISTENER_GROUP = san.tools.objectCreate(null);

                        $(document).sanRouter('add', $a.attr('data-route'));

                        return;
                    }

                    // 需登录和手机验证的频道
                    if (~('1-4|1-5|1-6'.indexOf($li.attr('data-mid')))) {
                        popupConfirm(JURL + ROUTE['signin'] + '/validate-phone.html');
                    }
                });

                // 添加标记
                $this.find('[data-url]').each(function(){
                    var $item = $(this),
                        url = $item.attr('data-url'),
                        href = $item.attr('href'),
                        $lv2 = null;
                    if (url) {
                        $item.append('<sup>*</sup>');
                    } else if (!~href.indexOf('void(0)')) {
                        $item.append('<sup>+</sup>');
                    }

                    if ($item.hasClass(opt.level3) && url || !~href.indexOf('void(0)')) {
                        $lv2 = $item.closest('.' + opt.menuDropList).prev();
                        if (!$lv2.find('sup').length) {
                            $item.closest('.' + opt.menuDropList).prev().append('<sup>*</sup>');
                        }
                    }
                });
               
            });
        }
    };

    $.fn.sanSideMenu = function(option){
        var sideMenu = san.tools.objectCreate(san.widget);
        return sideMenu.init(this, methods, arguments);
    };
})(jQuery);



// 如果href以#或javascript开头，返回true
function sanIgnoreHref(href){
    if (href && /(^#|^(javascript))/.test(href)){
        return true;
    }else{
        return false;
    }
}



/**
 * sanTabs
 * 标签页
 * @author: zhxming
 * HTML结构
 *     <div class="{config.wrapper}">
 *       <ul class="{config.tabs}">
 *           <li><a href="javascript:void(0);" [data-url=""]></a></li>
 *           ......
 *       </ul>
 *     </div>
 *     <div class="{config.container}">（应紧跟在选项卡san-tabs之后）
 *         <div class="{config.contentPanel}"></div>（标签页内容显示区域，至少一个，必须是.san-tabs-content的子元素）
 *         ......
 *     </div>
 * 1.当前项样式.current设置在<li>上；
 * 2.内容加载在.san-tabs-panel中，可有多个但必须包裹在.san-tabs-content中。
 *
 * 自定义属性：
 * data-tabs-index: 自动设置在<li>上，标签选项卡索引编号，从0开始。
 * data-tabs-count: 自动设置在<ul>上，标签选项卡总数（不包括被排除的选项卡）。
 * data-title：自动设置在<a>上，标签选项卡的文本内容。
 * data-show: 值：load（异步加载模式）||toggle（同步加载模式）||once（单次异步加载模式）。
 *            在选项卡(<li>)上的data-show：一般均自动添加。如果要允许选项卡内容可以多次（异步）加载，需手动为选项卡添加data-show="load"
 *            在内容容器（san-tabs-panel）上的data-show：：一般均自动添加。当type=mix时需与选项卡对应手动设置。
 * data-resolve：值： '0'||'1'。单次异步加载模式时，判断是否已加载过的标记，自动生成。
 */
;(function($) {
    'use strict';

    // 配置参数
    var config = {
        //标签选项卡，CLASS
        tabs: 'san-tabs-a',
        wrapper: 'san-tabs-wrapper',
        //标签页内容区，CLASS
        container: 'san-tabs-content',
        //标签页内容显示区，CLASS，container内部应该至少需要有一个panel
        contentPanel: 'san-tabs-panel',
        // 当前选中的标签选项卡，CLASS
        currentClass: 'current',
        // 选项卡默认的当前选中项，从1开始
        defaultItem: 1,
        // 要排除的选项卡，CLASS，给选项卡添加此CLASS将把它排除出sanTabs的控制
        excludeItem: 'exclude',
        /* 选项卡排列显示方式。list||table。
         * list： 默认。普通<li>结构。
         * table: 使用<li>结构模拟table结构。注意：此方式将改变选项卡的结构
         */
        layout: 'list',
        // layout=table时有效，标签选项卡的包裹容器
        layoutWrapper: 'san-tabs-a-table',
        // layout=table时有效，单元格内容（最小）间距（单侧值）
        layoutSpacing: 20,
        // 是否生成下拉选择框，并在满足条件时显示下拉选择框，隐藏标签页，
        select: false,
        // 下拉选择框前的文本
        selectLabel: '',
        // 选项卡是否等宽排列。layout=table时无效。
        equalWidth: false,
        // equalWidth=true，并且选项卡数量>=rowMin时等宽排列才生效
        rowMin: 4,
        // equalWidth=true有效，每行最大显示选项卡数量
        rowMax: 6,
        /* 内容加载模式：load||toggle||mix。
         *   load： 默认。异步加载模式。使用ajax方式加载内容。
         *   toggle: 同步加载模式。内容预先加载到多个.san-tabs-panel中，切换显示不同的.san-tabs-panel。
         *   mix：混合模式。各选项卡中既有异步加载模式也有同步加载模式，对应多个.san-tabs-panel。
         * 详见各模式加载方法的注释。
         */
        type: 'load',
        // 标签页内容的URL。当tyle=load和mix时有效。
        url: 'data-url',
        /* 是否启用单次异步加载模式。
         * 当type=load和mix时有效。
         * 单次加载模式时，不管点击几次选项卡，内容只运行一次ajax加载（成功返回）。
         * 单次异步加载模式的选项卡会自动生成标记data-show="once"。
         * 当once:true时，为选项卡设置data-show="load||once"，可作为例外将该选项卡设为多次或单次异步加载模式。
         */
        once: true,
        // GET || POST
        loadMethod: 'GET',
        cache: false,
        timestamp: true,
        overflowMask: true,
        //标签选项卡鼠标监听事件，默认click
        event: DEFAULT_EVENT,
        /* 触发鼠标监听事件后执行。$li: 当前选项卡。
         * 如要在触发事件后需要更新注入替换变量，将新的注入替换变量(对象)return。
         * 如果无需更新，则不用return，或return false。
         */
        onEvent: function($li){},
        /* 回调，初始化时执行。
         * 仅能保证获取到当前选项卡，不能保证内容的显示情况，涉及内容区时请使用onDone或onFail。
         * this：选项卡容器，$li: 当前选项卡。
         */
        onInit: function($li){},
        /* 回调，内容加载之前执行。
         * 仅异步加载模式时有效。
         * this：内容区容器（san-tabs-content），$li: 当前选项卡。
         */
        onBeforeLoad: function($li){},
        /* 回调，内容加载完成后执行。
         * 异步加载模式时，内容区加载成功后执行。同步加载模式时，内容区显示后执行。
         * this：内容区容器（san-tabs-panel），$li: 当前选项卡。
         */
        onDone: function($li){},
        /* 回调，内容加载失败后执行。
         * 异步加载模式时，内容区加载失败后执行。同步加载模式时，内容区无法显示（找不到内容区）时执行。
         * this：内容区容器（san-tabs-panel），$li: 当前选项卡。
         */
        onFail: function($li){},
        /* 是否允许注入替换。
         * 仅对异步加载的内容有效，即仅对data-show=load||once的内容容器有效。
         * 详见sanJumpto()注释。
         */
        inject: true,
        //注入替换变量。inject=true时有效。详见sanJumpto()注释。
        injectedVar: {},
        /* 是否启用响应媒体监听
         * 设为true时启用
         */
        mediaListening: false,
        mediaFormula: 'default-media',
        /* 回调方法。当监听到响应媒体变化时执行
         * 通过此回调方法，在响应变化发生时执行相应操作
         */
        onMediaChange: function(){}
    };

    var namespace = 'sanTabs',
        handleMark = 'data-tabs',
        isMoving = false;

    var methods = {
        /* 
         * 初始化
         * this: 标签选项卡(san-tabs)
         */
        init: function(option){
            return this.each(function(i){
                var $this = $(this),
                    opt = $.extend({}, config, option);
                var type = opt.type,
                    layout = opt.layout,
                    contentPanel = opt.contentPanel,
                    excludeItem = opt.excludeItem,
                    tabsId,
                    $wrapper = null,
                    $content = null,
                    $panel = null,
                    $clonePanel = null,
                    $table = null,
                    $select = null;

                tabsId = san.tools.uuid('san-tabs-');
                $this.attr(handleMark, tabsId);
                opt.tabsId = tabsId;

                isMoving = false;
                
                // ?temp
                var strTemp = '';
                strTemp = san.tools.trim($this.attr('class')).split(' ');
                opt.tabs = strTemp[0];
                if (!$this.parent().hasClass(opt.wrapper)) {
                    $this.wrap('<div class="'+ opt.wrapper + ' ' + strTemp[0] + '-wrapper"></div>');
                }

                $wrapper = $this.parent();
                if ($this[0].id) {
                    if (!$wrapper[0].id) {
                        $wrapper.attr('id', $this[0].id + '-wrapper');
                    }
                    $wrapper.attr('data-id', $this[0].id);
                }
                $content = $wrapper.nextAll('.' + opt.container + ':eq(0)');
                
                $this.data('options', opt);
                
                // 异步加载模式/混合加载模式的相关设置
                if (type == 'load'){
                    $panel = $content.children('.' + contentPanel + ':eq(0)');
                    $panel.attr('data-show', 'load');
                } else if (type == 'mix') {
                    $panel = $content.children('.' + contentPanel + '[data-show="load"]:eq(0)');
                }
                
                //初始化标签页
                var count = 0;
                // $this.find('li:not(.' + excludeItem + ')').each(function(i){
                $this.find('li').each(function(i){
                    var $li = $(this),
                        $a = $li.children('a'),
                        url = $a.attr(opt.url),
                        title = $a.attr('data-title'),
                        loadType = $li.attr('data-show'),
                        isExcludeItem = $li.hasClass(excludeItem);
                    count = i + 1;

                    // 选项卡索引
                    if (!isExcludeItem) {
                        $li.attr('data-tabs-index', i);
                    } else {
                        $li.attr('data-exclude-index', i);
                    }

                    if (!title) {
                        $a.attr('data-title', $a.text());
                    }

                    if (isExcludeItem) {return;}

                    // 同步加载模式时的相关设置
                    if (type == 'toggle'){
                        $content.children('.' + contentPanel + ':eq(' + i + ')').attr('data-tabs-index', i).attr('data-show', 'toggle');
                        return;
                    }

                    // 单次加载时的相关设置
                    if (url !== undefined){
                        if (opt.once){
                            // 设置单次/多次异步加载标记
                            var loadRegExp = /^(load|once)$/;
                            if (!loadRegExp.test(loadType)){
                                loadType = 'once';
                                $li.attr('data-show', loadType);
                            }
                            if (loadType == 'once'){
                                $li.attr('data-resolve', 0);
                                var _$panel = $content.children('.' + contentPanel + '[data-tabs-index="' + i + '"]');
                                if (!_$panel.length){
                                    $clonePanel = $panel.clone();
                                    $clonePanel.attr({
                                        'data-show': 'once',
                                        'data-tabs-index': i
                                    }).removeAttr('id');
                                    $content.children('.' + contentPanel + ':last').after($clonePanel);
                                }else{
                                    _$panel.attr('data-show', 'once');
                                }
                            }else{
                                $li.removeAttr('data-resolve');
                            }
                        }else{
                            $li.attr('data-show', 'load').removeAttr('data-resolve');
                        }
                    }

                    // 混合模式时的相关设置
                    if (type == 'mix' && url === undefined){
                        // $this.next('.' + opt.container).children('.' + contentPanel + '[data-show="toggle"]').each(function(v){
                        $content.children('.' + contentPanel + '[data-show="toggle"]').each(function(v){
                            var index = $(this).attr('data-tabs-index');
                            if (!index){
                                $(this).attr('data-tabs-index', i);
                                return false;
                            }
                        });
                        return;
                    }
                });
                
                //记录选项卡总数
                $this.attr('data-tabs-count', count);

                methods.build.call($this);

                //标签页绑定事件
                $this.off(opt.event + '.' + namespace, '[data-tabs-index]');
                $this.on(opt.event + '.' + namespace, '[data-tabs-index]', function(e, first){
                    if (isMoving) { return; }
                    e.preventDefault();
                    $(DOC).find('.hasDatepicker').each(function(){
                        $(this).blur();
                        $(this).datepicker('hide');
                    });
                    var $li = $(this);
                    if (!first && ($li.hasClass(opt.currentClass) || $li.hasClass(excludeItem))) {return false;}
                    
                    // 回调并更新注入替换变量
                    var newInject = opt.onEvent.call($this, $li);
                    if (opt.inject && newInject && typeof newInject === 'object'){
                        opt.injectedVar = $.extend({}, opt.injectedVar, newInject);
                        $this.data('options', opt);
                    }
                    methods.update.call($this, $li);
                });

                if (layout == 'table') {
                    $table = $this.nextAll('.' + opt.layoutWrapper);
                    $table.off(opt.event + '.' + namespace, '[data-tabs-index]');
                    $table.on(opt.event + '.' + namespace, '[data-tabs-index]', function(){
                        $this.find('[data-tabs-index="' + $(this).attr('data-tabs-index') + '"]').trigger(opt.event + '.' + namespace);
                    });
                }

                if (opt.select) {
                    $select = $this.nextAll('.san-tabs-select');
                    $select.off('change').on('change.' + namespace, function(){
                        var index = $select.find(':selected').attr('data-index');
                        $this.find('[data-tabs-index="' + index + '"]').trigger(opt.event + '.' + namespace);
                    });
                }

                if (opt.mediaListening) {
                    $this.attr('data-listener', 'media');
                    san.listener.duplicated($this[0], RESIZE_LISTENER_GROUP);
                    MEDIA_LISTENER_GROUP[tabsId] = $this[0];

                    var waitingTimer,
                        prevMedia = MEDIA_CASE,
                        curMedia,
                        mediaChange = false;
                    $this.off(MEDIA_LISTENER + '.' + namespace).on(MEDIA_LISTENER + '.' + namespace, function() {
                        clearInterval(waitingTimer);
                        waitingTimer = setInterval(function(){
                            if (GLOBE_INIT) {
                                clearInterval(waitingTimer);
                                curMedia = MEDIA_CASE;
                                // if (prevMedia === curMedia) {return false;}
                                mediaChange = prevMedia === curMedia ? false : true;
                                prevMedia = curMedia;
                                methods.resize.call($this, mediaChange);

                                opt.onMediaChange.call($this);
                            }
                        }, 10);
                    });
                }

                if (opt.event == 'touchend' && V_VW < MEDIA_RULE.M) {
                    var x1, x2, y1, y2;
                    $this.off('touchstart touchmove');
                    $this.on('touchstart.' + namespace, function(e) {
                        isMoving = false;
                        x1 = e.originalEvent.touches[0].pageX;
                        y1 = e.originalEvent.touches[0].pageY;
                    });
                    $this.on('touchmove.' + namespace,  function(e) {
                        x2 = e.originalEvent.touches[0].pageX;
                        y2 = e.originalEvent.touches[0].pageY;
                        if (Math.abs(x2 - x1) > 2 || Math.abs(y2 - y1) > 1){
                            isMoving = true;
                        }
                    });    
                }
                
                //设置选项卡默认选中项，如defaultItem未找到，选中第一项
                var defaultItem = parseInt(opt.defaultItem, 10) || 0;
                if (defaultItem){
                    defaultItem = Math.max(0, defaultItem - 1);
                }
                var $current = $this.find('[data-tabs-index="' + defaultItem + '"]');
                // methods.update.call($this, $current);
                $this.data('default', defaultItem);

                opt.onInit.call($this, $current);

                $current.trigger(opt.event + '.' + namespace, [true]);
            });
        },
        build: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    layout = opt.layout;

                if (opt.overflowMask && !opt.select) {
                    methods.buildMask.call($this);
                }

                if (layout == 'table') {
                    methods.buildTable.call($this);
                    return;
                }

                if (opt.select) {
                    methods.buildSelect.call($this);
                }

                if (opt.equalWidth && layout != 'table') {
                    methods.buildEqual.call($this);
                }
            });
        },
        buildSelect: function(droplist){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    layoutWrapper = opt.layoutWrapper,
                    $table = $this.nextAll('.' + layoutWrapper + ':eq(0)'),
                    $select = $this.nextAll('.san-tabs-select:eq(0)'),
                    strSelect = '', strDroplist = droplist || '';

                if ($select.length) {return;}

                if (!strDroplist) {
                    $this.find('li').each(function(i){
                        var $li = $(this);
                        strDroplist += '<option data-index="' + i + '">' + $li.find('span').text() + '</option>';
                    });
                }
                
                // strSelect += '<div class="san-tabs-select san-grid">';
                strSelect += '<div class="san-tabs-select san-grid" data-tabs-count="' + $this.attr('data-tabs-count') + '" data-tabs-id="' + ($this[0].id || '') + '" style="' + ($this.attr('style') || '') + '">';
                strSelect += '<div class="san-grid-l">';
                strSelect += '<label class="san-input-label';
                strSelect += opt.selectLabel ? '"' : ' NONE"';
                strSelect += '>' + opt.selectLabel + '</label>';
                strSelect += '</div>';
                strSelect += '<div class="san-grid-m">';
                strSelect += '<select class="san-select">' + strDroplist + '</select>';
                strSelect += '</div>';
                strSelect += '</div>';
                if ($table.length) {
                    $table.after(strSelect);
                } else {
                    $this.after(strSelect);
                }
                $select = $this.nextAll('.san-tabs-select:eq(0)');

                if (opt.mediaListening) {
                    $this.attr('data-layout', opt.mediaFormula);
                    $select.attr({
                        // 'data-listener': 'media',
                        'data-layout': opt.mediaFormula
                    });
                } else {
                    $this.attr('data-layout', 'select');
                    $select.attr('data-layout', 'select');
                }

                $select.data('options', opt);
            });
        },
        buildTable: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = null, layoutWrapper, excludeItem,
                    w, wr = 0, padding, 
                    tbl, ul = '<ul>', strDroplist = '', strSelect = '',
                    $table = null, $select = null;
                
                if (~IE_V && IE_V < 7 ) {return;}

                opt = $this.data('options');

                if (opt.mediaListening) {
                    $this.attr('data-layout', 'suspend');
                } else {
                    $this.removeAttr('data-layout');
                }

                layoutWrapper = opt.layoutWrapper;
                excludeItem = opt.excludeItem;
                w = $this.width(); 
                wr = 0; 
                padding = parseInt(opt.layoutSpacing, 10);
                $table = $this.nextAll('.' + layoutWrapper + ':eq(0)');

                if (!$table.length) {
                    tbl = '<div class="' + layoutWrapper + '" data-tabs-count="' + $this.attr('data-tabs-count') + '" data-tabs-id="' + ($this[0].id || '') + '" style="' + ($this.attr('style') || '') + '"></div>';
                    $this.after(tbl);
                    $table = $this.nextAll('.' + layoutWrapper + ':eq(0)');
                }

                $this.find('li').each(function(i){
                    var $li = $(this),
                        $a = $li.find('a'),
                        $text = $li.find('span'),
                        aw = 0,
                        text = $text.text(),
                        idx = parseInt($li.attr('data-tabs-index'), 10),
                        excludeIdx = 0,
                        shw = $li.attr('data-show'),
                        rsv = $li.attr('data-resolve'),
                        url = $a.attr(opt.url),
                        href = $a.attr('href'),
                        classList = '';

                    classList += $li.hasClass(opt.currentClass) ? ' current' : '';
                    classList += $li.hasClass(excludeItem) ? ' exclude' : '';
                    classList = san.tools.trim(classList);
                    
                    aw = parseFloat($li.outerWidth()) + 2;
                    wr = wr + aw;

                    if (wr > w){
                        ul += '</ul><ul>';
                        wr = aw;
                    }

                    ul += '<li';
                    ul += classList ? ' class="' + classList + '"' : '';

                    if (!isNaN(idx)){
                        ul += ' data-tabs-index="' + idx + '"';
                    } else if ($li.hasClass(excludeItem)) {
                        idx = parseInt($li.attr('data-exclude-index'), 10);
                        ul += ' data-exclude-index="' + idx + '"';
                    }
                    if (shw){
                        ul += ' data-show="' + shw + '"';
                    }
                    if (rsv !== undefined){
                        ul += ' data-resolve="' + rsv + '"';
                    }
                    ul += '><a href="' + href + '"';
                    if (url !== undefined){
                        ul += ' ' + opt.url + '="' + url + '"';
                    }
                    if ($li.hasClass(excludeItem) && $a.attr('target')) {
                        ul += ' target="' + $a.attr('target') + '"';
                    }
                    if (padding){
                        ul += ' style="padding-left: ' + padding + 'px; padding-right: ' + padding + 'px;"';
                    }
                    // ul += '><span>' + text + '</span></a>';
                    ul += '>' + $a.html() + '</a>';
                    ul += '</li>';

                    strDroplist += '<option data-index="' + idx + '">' + text + '</option>'
                });
                ul += '</ul>';

                $table.find('ul').remove().end().prepend(ul);

                if (opt.select) {
                    methods.buildSelect.call($this, strDroplist);
                }

                $table.find('ul:last').addClass('last fixedAuto');
                var wl = 0;
                $table.find('ul:last').children().each(function(){
                    wl += $(this).width();
                });
                if (wl >= w * 0.66666667){
                    $table.find('ul:last').removeClass('fixedAuto');
                }
                $table.data('options', opt);

                if (opt.mediaListening) {
                    $this.attr('data-layout', opt.mediaFormula);
                    $table.attr({
                        // 'data-listener': 'media',
                        'data-layout': opt.mediaFormula
                    });
                } else {
                    $this.attr('data-layout', 'table');
                    $table.attr('data-layout', 'table');
                }
            });
        },
        buildEqual: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'), rowLen = 0, ew;
                if (opt.layout == 'table'){return;}
                rowLen = $this.find('li').length;
                //超过最小显示数时，才等宽显示
                if (rowLen >= parseInt(opt.rowMin, 10)){
                    // 每行最大显示数
                    rowLen = Math.min(rowLen, parseInt(opt.rowMax, 10));
                    ew = 100 / rowLen + '%';
                    $this.addClass('san-tabs-equal');
                    $this.find('li').each(function(){
                        $(this).css({
                            'width': ew
                        });
                    });
                }
            });
        },
        buildMask: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $wrapper = $this.parent(),
                    w = 0,
                    mask = 'san-tabs-border-mask',
                    plusMask = false;

                if (opt.select) {return;}

                $this.children().each(function(){
                    w += $(this).outerWidth(true);
                    if (w > V_VW - SSZ) {
                        plusMask = true;
                        return false;
                    }
                });

                $this.attr('data-resize', 'true');
                san.listener.duplicated($this[0], RESIZE_LISTENER_GROUP);
                RESIZE_LISTENER_GROUP[opt.tabsId] = $this[0];

                if (plusMask) {
                    $wrapper.addClass(mask);
                } else {
                    $wrapper.removeClass(mask);
                }

                var waitingTimer;
                $this.on(RESIZE_LISTENER + '.' + namespace, function() {
                    clearInterval(waitingTimer);
                    waitingTimer = setInterval(function(){
                        if (GLOBE_INIT) {
                            clearInterval(waitingTimer);
                            methods.buildMask.call($this);
                        }
                    }, 10);
                });
                
            });
        },
        resize: function(mediaChange) {
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    layout = opt.layout;

                if (layout == 'table') {
                    if (V_VW >= MEDIA_RULE.M) {
                        methods.buildTable.call($this);
                    }
                    return;
                }
            });
        },
        /* 
         * 更新
         * this: 标签选项卡(san-tabs)
         * $li: 当前选项卡，jQuery对象
         */
        update: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    type = opt.type,
                    currentClass = opt.currentClass,
                    index = $li.attr('data-tabs-index'),
                    $table = null,
                    $select = null;
                
                if (!$li.length) return;

                $li.addClass(currentClass).siblings().removeClass(currentClass);

                if (opt.layout == 'table') {
                    $table = $this.nextAll('.' + opt.layoutWrapper);
                    $table.find('li').removeClass(currentClass);
                    $table.find('[data-tabs-index="' + index + '"]').addClass(currentClass);
                }

                if (opt.select) {
                    $select = $this.nextAll('.san-tabs-select');
                    $select.find('[data-index="' + index + '"]').prop('selected', true);
                }
                
                if (type == 'load'){
                    methods.load.call($this, $li);
                }else if (type == 'toggle'){
                    methods.toggle.call($this, $li);
                }else if (type == 'mix'){
                    methods.mix.call($this, $li);
                }
            });
        },
        /* 
         * ajax方式加载标签页内容（仅一个内容区，对其重复加载要显示的内容）
         * 普通模式（多次加载模式）下仅需一个内容区即可。单次加载模式（once:true）时，内容加载到与选项卡相对应的内容区内（自动生成，data-show=once）
         * 约束：
         * 必须遵循HTML结构
         * this: 标签选项卡(san-tabs)
         * $li: 当前选项卡，jQuery对象
         */
        load: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    contentPanel = opt.contentPanel,
                    once = opt.once,
                    index = parseInt($li.attr('data-tabs-index'), 10),
                    loadType = $li.attr('data-show'),
                    $wrapper = $this.parent(),
                    $content = $wrapper.nextAll('.' + opt.container + ':eq(0)'),
                    $panel = null;

                // 获取内容容器，单次/多次加载时内容容器不同
                if (once && loadType == 'once'){
                    $panel = $content.children('.' + contentPanel + '[data-show="once"][data-tabs-index="' + index + '"]');
                }else{
                    $panel = $content.children('.' + contentPanel + '[data-show="load"]:eq(0)');
                    // 清空内容容器
                    // $panel.empty();
                }

                // 激活内容容器
                $panel.addClass('active').siblings('.' + contentPanel).removeClass('active');
                
                // 单次加载且已加载过时
                if (once && loadType == 'once' && $li.attr('data-resolve') == '1'){
                    san.listener.mediaQuery();
                    return;
                }

                //加载内容
                var u = $li.find('a').attr(opt.url);
                $panel.sanJumpto({
                    url: u,
                    type: opt.loadMethod,
                    cache: opt.cache,
                    timestamp:  opt.timestamp,
                    inject: opt.inject,
                    injectedVar: opt.injectedVar,
                    onBefore: function(){
                        //$panel.empty();
                        opt.onBeforeLoad.call($panel, $li);
                    },
                    onDone: function(){
                        // 单次加载时
                        if (once && loadType == 'once'){
                            $li.attr('data-resolve', 1);
                        }
                        opt.onDone.call($panel, $li);
                    },
                    onFail: function(){
                        // 单次加载时
                        if (once && loadType == 'once'){
                            $li.attr('data-resolve', 0);
                        }
                        opt.onFail.call($panel, $li);
                    }
                });
            });
        },
        /* 
         * 切换显示标签页内容（多个标签页内容同时加载，切换显示/隐藏对应的内容）
         * 约束：
         * 必须遵循HTML结构：选项卡和内容容器.san-tabs-panel按照顺序一一对应
         * this: 标签选项卡(san-tabs)
         * $li: 当前选项卡，jQuery对象
         */
        toggle: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    contentPanel = opt.contentPanel,
                    index = parseInt($li.attr('data-tabs-index'), 10),
                    $wrapper = $this.parent(),
                    $content = $wrapper.nextAll('.' + opt.container + ':eq(0)'),
                    $panel = $content.children('.' + contentPanel + '[data-tabs-index="' + index + '"]'),
                    $dtd = $.Deferred();
                
                //回调
                $.when(waiting($dtd)).done(function(){
                    opt.onDone.call($panel, $li);
                    san.listener.mediaQuery();
                }).fail(function(){
                    opt.onFail.call($panel, $li);
                });
                
                function waiting($dtd){
                    if (typeof $panel[0] !== 'undefined'){
                        //激活对应的内容区
                        $panel.addClass('active').siblings('.' + contentPanel).removeClass('active');
                        // $panel.siblings('.' + contentPanel + '[data-show="load"]').empty();
                        $dtd.resolve();
                    }else{
                        $dtd.reject();
                    }
                    return $dtd.promise();
                }
                
            });
        },
        /* 
         * 混合显示（既有ajax方式加载，又有切换显示/隐藏内容区）
         * 约束：
         * 带有data-url属性的选项卡，即判断为使用ajax方式，不管值是否为空。
         * 为使用ajax方式的.san-tabs-panel，添加属性data-show="load";该.san-tabs-panel一个即可，也仅第一个有效。
         * 为要切换显示的.san-tabs-panel添加属性data-show="toggle"，数量和顺序须和选项卡（非ajax方式的）一一对应
         * this: 标签选项卡(san-tabs)
         * $li: 当前选项卡，jQuery对象
         */
        mix: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    url = $li.children().attr(opt.url);
                if (url !== undefined){
                    methods.load.call($this, $li);
                }else{                   
                    methods.toggle.call($this, $li);
                }
            });
        },
        /*
         * 重置到初始状态
         */
        reset: function(){
            return this.each(function(){
                var $this = $(this),
                    index = $this.data('default'),
                    $d = $this.find('[data-tabs-index="' + index + '"]');
                methods.update.call($this, $d);
            });
        },
        /*
         * htmlDEMO补丁
         * 此方法仅用于本htmlDEMO内使用，实际开发中无需调用。
         */
        htmlDEMOPlus: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    type = opt.type,
                    isTable = opt.layout == 'table' ? true : false;

                $this.find('li').each(function(i){
                    var $li = $(this),
                        $a = $li.children('a'),
                        url = $a.attr(opt.url),
                        index = parseInt($li.attr('data-tabs-index'), 10);
                    var hasContent = false;

                    if (url || !sanIgnoreHref($a.attr('href'))){
                        hasContent = true;
                    }
                    if (type == 'toggle' || type == 'mix'){
                        var $togglePanel = $this.nextAll('.' + opt.container + ':eq(0)').children('.' + opt.contentPanel + '[data-tabs-index="' + index + '"][data-show="toggle"]');
                        if ($togglePanel.length && !!san.tools.trim($togglePanel.html())){
                            hasContent = true;
                        }
                    }

                    if (hasContent){
                        $a.find('sup').remove();
                        $a.append('<sup class="p-0">*</sup>');
                        var _$a = null;
                        if (isTable && $this.next('[data-tabs-id]').length) {
                            _$a = $this.next('.' + opt.layoutWrapper).find('[data-tabs-index="' + index + '"]').children('a');
                            _$a.find('sup').find('sup').remove();
                            _$a.append('<sup class="p-0">*</sup>');
                        }
                    }
                });
            });
        }
    };

    $.fn.sanTabs = function(option) {
        var tabs = san.tools.objectCreate(san.widget);
        return tabs.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanDatasheet
 * 数据表格
 * @author: zhxming
 * 约束：
 * 1.必须遵循指定的HTML结构和json数据结构，详见范例中的HTML模板和json数据模板。
 * 2.table必须有thead和tbody标签，在thead中指定要显示的数据项名称，在tbody中显示对应数据项的值。
 * 3.需为数据项单元格（包括thead和tbody）添加.cell样式。
 * 自定义属性：
 * data-count: 总数据行数，从1起。自动生成在数据表容器上。
 * data-date: 数据日期，值来自json文件。自动生成在数据表容器上。
 * data-url: 数据源url。自动生成在数据表容器上,如果数据源来自本地变量，仅显示'local'。
 * data-row: 数据行索引号，从0起。自动生成在tbody的数据行（tr）上。
 * data-name： 指定该列的数据项名称，对应json文件。
 *             必须手动在thead的单元格中设定。当获取数据后自动复制到tbody的对应单元格上。
 *             多个值时使用/分隔。
 *             （多个值时，即可拼合成一个值显示在一个元素内，也可多个值分开显示，一个值一个元素。）
 *             （当多个值时，其中有值带有附加标签，必须分开显示。）
 *             （是拼合还是分开显示，全表格全数据一致。）
 *             当有子记录时（属性的值仍是个对象数组），使用@设置分隔。
 *             比如termEN@interestRateSwapList，即表示termEN是interestRateSwapList中的一个子属性。
 * data-serial： 多行表头时（thead中）指定数据列顺序（单行表头下无效）。需手动在thead的单元格中设定，从1开始。
 * data-value： 用于存放数据项的值（对应data-name）。自动生成在tbody单元格中。
 *              单元格中可能会存在其它元素，因此要获取数据值时应使用此属性。
 *              当单元格数据由多个值组成，各值之间以'{/}'分割。
 * data-value-count：显示单元格内的.cell-value元素个数。
 * data-value-index：各单元格内.cell-value元素的索引值。附加标签拥有与对应.cell-value元素相同的索引值。
 * data-sp： 表特殊单元格。需手动在表头（thead）单元格中设置。值如下：
 *           lineNumber：表示该列是行号列。 lineNumer设为true时有效。
 * data-tag: 表该单元格带有附加标签。需手动在表头（thead）单元格中设置。值如下：
 *           flag: 货币标识标签（国旗）。 currencyTag设为true时有效，默认在数据值元素前显示。
 *           priceLimit：涨跌幅标签。 priceLimitTag设为true时有效。
 * data-tag-target: 表附加标签的取值数据项名称。需手动在表头（thead）单元格中设置，同时该属性会自动复制到tbody中对应单元格上。
 *           flag时data-tag-target应是图标路径
 *           priceLimit时data-tag-target应是表示涨跌标识位的数据项名称。
 *           多个值时，用'/'分割并与data-name相对应。无附加标签的值只添加/即可。
 *           比如：两个数据项只有其中一项有涨跌幅标记：
 *                 data-name="price/bp", data-tag-target="/bpDouble"
 *                 data-name="bp/price", data-tag-target="bpDouble/"
 *                 两个数据项均有涨跌幅标记：
 *                 data-name="price/bp", data-tag-target="priceDouble/bpDouble"
 * data-tag-position: 表附加标签的显示位置（相对于数据值元素），只有left（默认）和right两个值。
 * data-blank: 空行标记。
 * 注意：
 * data-name、data-tag-target和data-value是相互对应的。但data-value的分割符是'{/}'，另两者分隔符是'/'。
 */
;(function($){
    'use strict';

    var config = {
        //CLASS，数据表容器
        sheet: 'san-datasheet',
        //CLASS，数据表表格容器，一个数据表中可能存在多个数据表格
        sheetBody: 'san-sheet',
        // CLASS，加载失败时显示信息容器
        sheetFail: 'san-sheet-error',
        //CLASS，数据单元格（存放数据名或值的单元格）
        cell: 'cell',
        //CLASS，数据值存放容器
        cellValue: 'cell-value',
        //关键数据（即主数据列）的索引号，从0开始
        cellKey: 0,
        //允许换行
        wrapAllowed: false,
        //表格行间隔色
        alternating: true,
        alternatingClass: 'san-sheet-alternating',
        //行号，同时需要在表头对应单元格设置data-sp="lineNumber"属性
        lineNumber: false,
        //货币标识标签（国旗）。 同时需要在表头对应单元格设置data-tag="flag"属性
        currencyTag: false,
        //货币标识标签样式名。注意这是一组复合CLASS（对应货币名/对），请参看CSS写法
        currencyTagClass: 'san-icon-flag',
        //货币标识标签与货币值之间的间距（margin-right）
        currencyTagSpacing: 10,
        //涨跌幅标签，同时需要在表头对应单元格设置data-tag="priceLimit"属性
        priceLimitTag: false,
        /* 涨跌幅标签样式名。注意这是一组复合CLASS，请参看CSS写法。
         * [主CLASS, 涨标签CLASS, 跌标签CLASS, 上涨时的文本样式CLASS, 下跌时的文本样式CLASS]
         * 前3个CLASS设置于标签容器上（必须），后2个样式设置于父容器上（可选）
         */
        priceLimitTagClass: ['san-icon', 'san-icon-up', 'san-icon-down', 'text-up', 'text-down'],
        //涨跌幅标签与数据值之间的间距（margin-left/right）
        priceLimitTagSpacing: 2,
        //数据来源。值：'local'（本地）和'remote'（默认，远程）
        dataSource: 'remote',
        //数据源地址。 dataSource='remote'时是地址链接， dataSource='local'时是数据变量
        url: '',
        //数据源返回的数据类型
        dataType: 'json',
        //数据源是访问请求时，是否携带时间戳，默认携带
        timestamp: true,
        //自定义属性，用于指定当列要展示的数据项，同时有多个数据项时时，以/分隔
        dataField: 'data-name',
        dataFieldPlus: 'data-name-plus',
        // json数据中的数据项来源。即data-name指定的数据项来自json数据对象中的哪个属性，默认取自records属性。
        dataJsonFieldSource: 'records',
        /* 使用本地数据源时，使用此方法可对数据源数据进行再加工
         * 比如使用一个url请求获取数据，在分批加载生成进多个数据表格时。
         * 参数：
         * data - 从数据源获得的数据
         * 作用域：
         * this - 数据表sheet
         * 返回值（必需）：要返回一个对象，该对象结构应该原数据相同
         *        比如 {'head': newdata['head'], 'data': newdata['data'], 'records': newdata['recordes']}
         */
        onLocalLoad: function(data){},
        /* 调取数据处理方法，返回要展示的数据（包括显示格式）
         * 参数：
         * data - $.ajax返回的数据
         * 作用域：
         * this - 数据表sheet
         * 返回值（必需）：{'newData': '', 'count': '', date: ''}
         *      newData - 处理完后返回的数据
         *      count - 记录总数 （该值将被设置在数据表格的data-count属性上）
         *      date - 数据生成时间 （该值将被设置在数据表格的data-date属性上）
         */
        dataHandler: function(data){},
        /* 数据加载前执行（数据请求发起前）
         * 作用域： this - 数据表sheet
         */
        onLoad: function(){},
        /* 数据加载成功后执行（DOM生成之后）
         * 作用域： this - 数据表sheet
         */
        onDone: function(){},
        /* 数据加载失败后执行
         * 作用域： this - 数据表sheet
         * 该方法在数据获取失败或json数据中records值为空时执行
         */
        onFail: function(){},
        onAlways: function(){},
        // 定时刷新
        autoRefresh: false,
        // 定时刷新间隔（毫秒）
        autoRefreshInterval: 6000,
        //高亮显示数值变化的单元格
        cellHighlight: false,
        //高亮显示效果对应CLASS名
        cellHighlightClass: 'highlight',
        //高亮效果持续时间（毫秒）
        cellHighlightDuration: 500,
        //将数据表分成两栏显示
        towColumns: false,
        //两栏时数据按序横向分组。即偶数一列，奇数一列。
        towColumnsAburton: false,
        //当记录总数为奇数时为第二栏补充一个空行
        towColumnsRowFill: false,
        //行滚动
        scroller: false,
        //行滚动时，固定不滚动的行数
        scrollFixedRows: 8,
        //行滚动时，每次滚动的行数
        scrollRows: 2,
        //滚动持续时间
        scrollDuration: 500,
        //滚动间隔
        scrollInterval: 4000,
        maskLayer: false,
        maskOption: null,
        // 数据表格（table）的宽度。number || 'auto'（默认），单位px。
        width: 'auto',
        //固定表格部件
        fixedLayout: false,
        /* 固定部件类型。
         * fixedLayout=true时有效。 值（String）如下：
         * header： 固定表头（仅thead部分），默认。
         * column： 固定列（左起）
         * all： 同时固定表头和列
         */
        fixedLayoutType: 'header',
        /* 固定宽度
         * fixedLayout=true && fixedLayoutType = column || all 时有效。
         * number || 'auto'（默认），值优先于width，如果为'auto'将取width的值。
         */
        fixedBodyWidth: 'auto',
        /* 固定高度
         * fixedLayout=true && fixedLayoutType = header || all 时有效。
         * number || 'auto'（默认）。
         */
        fixedBodyHeight: 'auto',
        /* 固定列数
         * fixedLayout=true && fixedLayoutType = column || all 时有效。
         * number，默认1列。
         */
        fixedColNumber: 1,
        /* 是否启用响应媒体监听
         * 设为true时启用，并为数据表格添加属性data-listener="media"。
         */
        mediaListening: false,
        /* 回调方法。当监听到响应媒体变化时执行
         * 通过此回调方法，在响应变化发生时执行相应操作
         * 如要重置数据表格的参数，返回一个option集合对象。其格式如下：
         * return {
         *     '[media]': {...}    对应各响应区间尺寸，[media]的值：XL || L || M || S || XS
         *     'default' : {...}  并不需要每个响应区间都设置，缺省的响应区间即使用default的值
         * }
         */
        onMediaChange: function(){}
    };

    var namespace = 'sanDatasheet',
        handleMark = 'data-datasheet',
        clearTime = {
            autoRefresh: null,
            scroller: null,
            resize: null
        },
        _st = 0,
        _sl = 0;

    var methods = {
        /**
         * 初始化
         */
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this),
                    $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)'),
                    sheetId;

                _st = 0;
                _sl = 0;

                sheetId = san.tools.uuid('san-datasheet-');
                opt.sheetId = sheetId;
                $this.attr(handleMark, sheetId);

                if (opt.mediaListening) {
                    $this.attr('data-listener', 'media');
                    san.listener.duplicated($this[0], MEDIA_LISTENER_GROUP);
                    MEDIA_LISTENER_GROUP[sheetId] = $this[0];
                }
                
                var w = parseInt(opt.width, 10);
                if (w){
                    $sheetBody.addClass('OA').find('table').css('width', w + 'px');
                }

                if (!$sheetBody.find('tbody').length){
                    $sheetBody.find('table').append('<tbody></tbody>');
                }
                
                var $head = $sheetBody.find('thead');
                
                // 要展示的数据项（按HTML结构中的先后顺序）集合
                var field = [],
                    fieldPlus = [],
                    fieldItem = null,
                    //单元格class集合
                    cellClass = [];
                var multiHead = $head.find('tr').length > 1 ? true : false;
                var $cols = multiHead ? $head.find('[data-serial]') : $head.find('td, th');
                var cellLength = $cols.length;

                $cols.each(function(i){
                    var $serial = $(this),
                        serial = multiHead ? parseInt($serial.attr('data-serial'), 10) - 1 : i;
                    if (!$serial.hasClass(opt.cell)) {$serial.addClass(opt.cell)};
                    fieldItem = $serial.attr(opt.dataField);
                    fieldItem = fieldItem ? fieldItem.split('/') : [];
                    // field.push(fieldItem);
                    field[serial] = fieldItem;

                    fieldItem = $serial.attr(opt.dataFieldPlus);
                    fieldItem = fieldItem ? fieldItem.split('/') : [];
                    // fieldPlus.push(fieldItem);
                    fieldPlus[serial] = fieldItem;
                    fieldItem = null;

                    // ie8-
                    if (i == 0) {
                        $serial.addClass('cell-first');
                    }
                    if (i == cellLength - 1) {
                        $serial.addClass('cell-last');
                    }
                    cellClass.push($serial.attr('class'));
                });

                //绑定数据
                $this.data({
                    'opt': opt,
                    'cellClass': cellClass,
                    'field': field,
                    'fieldPlus': fieldPlus,
                    'paireChange': ''
                });

                //加载数据
                // methods.load.call($this);

                //自动刷新
                clearTime.autoRefresh = setTimeout(function(){
                    if (opt.autoRefresh){
                        refreshTimer();
                    }else{
                        methods.load.call($this)
                    }
                }, 1);

                function refreshTimer(){
                    methods.refresh.call($this, opt.url);
                    clearTime.autoRefresh = setTimeout(refreshTimer, opt.autoRefreshInterval);
                }

                if (opt.mediaListening) {
                    var waitingTimer,
                        prevMedia = MEDIA_CASE;
                    $this.off(MEDIA_LISTENER + '.' + namespace).on(MEDIA_LISTENER + '.' + namespace, function(e, enforce) {
                        clearInterval(waitingTimer);
                        waitingTimer = setInterval(function(){
                            if (GLOBE_INIT && $this.attr('data-status') == 'done') {
                                clearInterval(waitingTimer);
                                var mediaList = null,
                                    curMedia = MEDIA_CASE,
                                    newOpt = null;
                                enforce = enforce === true ? true : false;
                                mediaList = opt.onMediaChange.call($this);
                                // if (prevMedia === curMedia && !enforce) {return false;}
                                if (prevMedia === curMedia && prevMedia == 'XL' && !enforce) {return false;}
                                // if ((RESIZE_IGNORE || prevMedia === curMedia && prevMedia == 'XL') && !enforce) {return false;}
                                // mediaList = opt.onMediaChange.call($this)
                                prevMedia = curMedia;
                                if (mediaList && san.tools.type(mediaList) === 'object') {
                                    if (mediaList[curMedia]) {
                                        newOpt = mediaList[curMedia];
                                    } else {
                                        newOpt = mediaList['default'];
                                    }
                                }
                                
                                methods.resize.call($this, newOpt);
                            }
                        }, 10);
                    });

                    if (MEDIA_CASE != 'XL') {
                        $this.trigger(MEDIA_LISTENER + '.' + namespace, [true]);
                    }
                }

            });
        },
        /**
         * 加载数据（远程或本地）
         * this - 数据表sheet
         */
        load: function(){
            return this.each(function(){
                // for setTimeout 
                if (!$(this).length || !$(this).data('opt')) return;

                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = null,
                    maskLayer = opt.maskLayer;
                //对应数据项
                var field = $this.data('field'),
                    fieldPlus = $this.data('fieldPlus');

                //对应class值
                var cellClass = $this.data('cellClass');
                //新旧比对值
                var pairChange = $this.data('pairChange'),
                    pairNew = '';
                var jsonRecords = null;
                
                $this.attr('data-status', 'loading');

                //获取远程数据
                if (opt.dataSource == 'remote'){
                    $.ajax({
                        type: 'POST',
                        cache: false,
                        url: opt.timestamp ? san.tools.urlTimestamp(opt.url) : opt.url,
                        dataType: opt.dataType,
                        beforeSend: function(){
                            if (maskLayer) {
                                if (opt.maskOption && san.tools.type(opt.maskOption) == 'option') {
                                    $this.sanMaskLayer(opt.maskOption);
                                } else {
                                    $this.sanMaskLayer();
                                }
                            }

                            $this.find('.' + opt.sheetFail).remove();
                            //回调
                            opt.onLoad.call($this);
                        }
                    }).done(function(_data){
                        var data = (typeof _data == 'string') ? $.parseJSON(_data) : _data;
                        //生成HTML
                        var $state = $.Deferred();
                        $.when(waiting(data, $state)).done(function(){
                            // alert('4- ' + $state.state());
                            //高亮
                            if (opt.cellHighlight){
                                setTimeout(function(){
                                    $this.find('.' + opt.cellHighlightClass).removeClass(opt.cellHighlightClass);
                                }, opt.cellHighlightDuration);
                            }
                            $this.attr('data-status', 'done');

                            san.listener.duplicated($this[0], SCROLL_LISTENER_GROUP);
                            SCROLL_LISTENER_GROUP[opt.sheetId] = $this[0];
                            methods.suspendBar.call($this);

                            //回调
                            opt.onDone.call($this);
                        });
                    }).fail(function(data){
                        //console.log('#' + $this.attr('id') + ': 获取数据失败！');
                        methods.loadFail.call($this, '获取数据失败!');
                        $this.attr('data-status', 'fail');
                        opt.onFail.call($this);
                    }).always(function(){
                        if (maskLayer) {
                            $this.sanMaskLayer('remove');
                        }
                        opt.onAlways.call($this);
                    });
                    return;
                }

                //获取本地数据
                if (opt.dataSource == 'local'){
                    $this.find('.' + opt.sheetFail).remove();
                    //获取数据
                    var data = (typeof opt.url == 'string') ? $.parseJSON(opt.url) : opt.url;
                    //回调
                    opt.onLoad.call($this);
                    // console.log('1--local');
                    var $loadState = $.Deferred();
                    $.when(localStandby(data, $loadState)).done(function(){
                        // 回调
                        var data2 = opt.onLocalLoad.call($this, data);
                        if (data2) {data = data2;}

                        // console.log('3--local--done-- ' + $loadState.state());
                        //生成HTML
                        var $state = $.Deferred();
                        $.when(waiting(data, $state)).done(function(){
                            // console.log('4--done-- ' + $state.state());
                            //高亮
                            if (opt.cellHighlight){
                                setTimeout(function(){
                                    $this.find('.' + opt.cellHighlightClass).removeClass(opt.cellHighlightClass);
                                }, opt.cellHighlightDuration);
                            }
                            $this.attr('data-status', 'done');

                            san.listener.duplicated($this[0], SCROLL_LISTENER_GROUP);
                            SCROLL_LISTENER_GROUP[opt.sheetId] = $this[0];
                            methods.suspendBar.call($this);

                            //回调
                            opt.onDone.call($this);
                        }).always(function(){
                            opt.onAlways.call($this);
                        });
                    }).fail(function(){
                        // console.log('3---fail ' + $loadState.state());
                        $this.attr('data-status', 'fail');
                        //回调
                        opt.onFail.call($this);
                        opt.onAlways.call($this);
                    });
                    return;
                }

                //准备本地数据
                function localStandby(data, $loadState){
                    // console.log('1--local--state-- ' + $loadState.state());
                    //数据记录不存在，中止
                    if (!data){
                        methods.loadFail.call($this, '获取数据失败!');
                        $loadState.reject();
                        return $loadState.promise();
                    }
                    $loadState.resolve();
                    return $loadState.promise();
                }

                //获取格式化后的数据并生成HTML
                function waiting(data, $state){
                    var dType = opt.dataType.toLocaleLowerCase();
                    if (dType == 'json'){
                        //获取格式化后的新数据值
                        var dataReturn = {
                            'records': null,    // 全部数据记录
                            'newData': null,    // 要显示的数据记录
                            'count': 0,         // 记录数
                            'date': ''          // 时间
                        };
                        dataReturn = $.extend({}, dataReturn, opt.dataHandler.call($this, data));
                        
                        //比对值比对
                        //数据中没有data或数据源是local时不执行
                        //相等时，更新单元格内容；
                        //不相等时，表示记录显示结构发生变化（比如先后次序，记录数等），此时将重构数据表
                        var update = false;
                        var dataInData = data['data'];
                        if (!san.tools.isEmptyObject(dataInData)){
                            update = recordsUpdate.call($this, dataInData['pairChange']);
                        }
                        // console.log('1--start-- ' + $state.state());
                        // 更新单元格
                        if (update){
                            // console.log('3--update-- ' + $state.state());
                            $.each(dataReturn.newData, function(n, v){
                                //遍历所有table中的所有tr
                                $this.find('tr[data-row]').each(function() {
                                    var $tr = $(this);
                                    var keyValue = $tr.find('.' + opt.cell + ':eq(' + opt.cellKey + ')').attr('data-value');
                                    keyValue = keyValue.replace(/\{\/\}/g, '');
                                    if (keyValue == v[opt.cellKey]){
                                        $tr.find('.' + opt.cell).each(function(i) {
                                            var $cell = $(this),
                                                cells = $cell.find('.' + opt.cellValue).length > 1 ? true : false,
                                                value = ($cell.attr('data-value')).split('{/}'),
                                                newValue = san.tools.isArray(v[i])? v[i] : san.tools.trim(v[i]).split('{/}'),
                                                _value = value.join('/'),
                                                _newValue = newValue.join('/');

                                            if (_value != _newValue) {
                                                // cell内有多个cellvalue
                                                if (cells) {
                                                    var valueIndex = 0,
                                                        valueLen = value.length,
                                                        target = $cell.attr('data-tag-target');
                                                    if (target) {target = target.split('/');}
                                                    for (; valueIndex < valueLen; valueIndex++) {
                                                        $cell.find('.' + opt.cellValue + '[data-value-index="' + valueIndex + '"]').text(newValue[valueIndex]);
                                                        //更新涨跌幅标签
                                                        if (opt.priceLimitTag && target){
                                                            var sign = methods.priceLimitJudge.call($this, dataReturn.records[n][target[valueIndex]]);
                                                            methods.priceLimitRefresh.call($this, $cell, valueIndex, sign, opt.priceLimitTagClass);
                                                        }
                                                    }
                                                    $cell.attr('data-value', newValue.join('{/}'));
                                                // cell内只有一个cellvalue
                                                } else {
                                                    $cell.find('.' + opt.cellValue).text(_newValue).end().attr('data-value', newValue.join('{/}'));
                                                    // 更新涨跌幅标签
                                                    var target = $cell.attr('data-tag-target');
                                                    if (opt.priceLimitTag && target){
                                                        var sign = methods.priceLimitJudge.call($this, dataReturn.records[n][target]);
                                                        methods.priceLimitRefresh.call($this, $cell, 0, sign, opt.priceLimitTagClass);
                                                    }
                                                }
                                                //高亮
                                                if (opt.cellHighlight){
                                                    $cell.addClass(opt.cellHighlightClass);
                                                }
                                            }
                                        });
                                    }
                                });
                            });
                            // console.log('3--update--' + $state.state());
                            $state.resolve();
                            return $state.promise();
                        }

                        // 重置
                        var noRrecords = false;
                        if (!dataReturn.newData.length){
                            methods.loadFail.call($this, '数据为空!');
                            noRrecords = true;
                        }else{
                            methods.clearSheet.call($this, false);
                        }
                        
                        // console.log('2--new-- ' + $state.state());
                        $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)');

                        // 重建数据表
                        var str = '', _str = '';
                        var dataIndex, dataLen, dataValue, fieldValue, fieldPlusValue; 
                        $.each(dataReturn.newData, function(n, v){
                            str += '<tr data-row="' + n + '"';
                            if (!san.tools.trim(v.join(''))){
                                // 空行
                                str += ' data-blank="1"';
                            }
                            str += '>';

                            fieldPlusValue = [];
                            var pi = 0, pl = fieldPlus.length, pv,
                                pr = san.tools.type(dataReturn.records) === 'array' && dataReturn.records[n];
                            if ((fieldPlus || pl > 0) && pr) {
                                for (; pi < pl; pi++) {
                                    pv = fieldPlus[pi];
                                    if (pv.length > 1) {
                                        var _pi = 0, _pl = pv.length, _pv = '';
                                        for (; _pi < _pl; _pi++) {
                                            if (_pi > 0) {_pv += '{/}';}
                                            if (!pr[pv[_pi]] || san.tools.type(pv[_pi]) === 'object' || san.tools.type(pv[_pi]) === 'array') {
                                                _pv += '';
                                            } else {
                                                _pv += pr[pv[_pi]];
                                            }
                                        }
                                        fieldPlusValue.push(_pv);
                                    } else {
                                        if (!pr[pv] || san.tools.type(pr[pv]) === 'object' || san.tools.type(pr[pv]) === 'array') {
                                            fieldPlusValue.push('');
                                        } else {
                                            fieldPlusValue.push(pr[pv]);
                                        }
                                    }
                                }
                            }

                            dataIndex = 0, dataLen = v.length;
                            for(; dataIndex < dataLen; dataIndex++) {
                                dataValue = v[dataIndex];
                                fieldValue = field[dataIndex];

                                if (fieldPlusValue[dataIndex]) {
                                    _str += ' data-name-plus="' + fieldPlus[dataIndex].join('/') + '"';
                                    _str += ' data-value-plus="' + san.tools.getCharEntity(fieldPlusValue[dataIndex]) + '"';
                                } else {
                                    _str = '';
                                }

                                str += '<td class="' + cellClass[dataIndex] + '"';
                                // data-name="" ?
                                // if (fieldValue.length) {
                                    str += ' data-name="' + fieldValue.join('/') + '"';
                                    var regHtml = /^{{html}}/i;
                                    // 是数组时，生成多个cell-value元素。是字符串时在一个cell-value元素内显示数据
                                    if (san.tools.isArray(dataValue)){
                                        var vi = 0, vLen = dataValue.length;
                                        str += ' data-value="' + san.tools.getCharEntity(dataValue.join('{/}')) + '" data-value-count="' + vLen + '"';
                                        str += _str + '>';
                                        for (; vi < vLen; vi++){
                                            if (vi > 0) {
                                                str += '/';
                                            }
                                            str += '<span class="' + opt.cellValue + '" data-value-index="' + vi + '" title="' + san.tools.getCharEntity(dataValue[vi]) + '">' + dataValue[vi] + '</span>';
                                        }
                                    } else if (regHtml.test(dataValue)) {
                                        dataValue = san.tools.trim(dataValue).replace(regHtml, '');
                                        str += ' data-value-count="1"';
                                        str += _str + '>';
                                        str += '<span class="' + opt.cellValue + '" data-value-index="0">' + dataValue + '</span>';
                                    } else {
                                        dataValue = san.tools.trim(dataValue);
                                        var _dataValue = dataValue.replace('{/}', '/');
                                        str += ' data-value="' + san.tools.getCharEntity(dataValue) + '"';
                                        str += ' data-value-count="1"';
                                        str += _str + '>';
                                        str += '<span class="' + opt.cellValue + '" data-value-index="0" title="' + san.tools.getCharEntity(_dataValue) + '">' + _dataValue + '</span>';
                                    }
                                // } else {
                                //     str += '>'
                                // }
                                str += '</td>';
                            }
                            str += '</tr>';
                        });
                        
                        $sheetBody.find('tbody').html(str);
                        
                        $this.attr('data-count', dataReturn.count);
                        $this.attr('data-date', dataReturn.date);
                        $this.attr('data-url', opt.dataSource == 'local' ? 'local' : opt.url);

                        if (!san.tools.isEmptyObject(dataInData)){
                            $this.data('pairChange', dataInData['pairChange']);
                        }

                        //允许换行
                        if (opt.wrapAllowed && !opt.scroller){
                            $this.find('.' + opt.sheetBody).addClass('san-sheet-wrap');
                        }
                        //添加行号
                        //注意此时thead和tbody单元格数量不匹配，table需要规整结构，需优先执行
                        if (opt.lineNumber){
                            methods.lineNumber.call($this);
                        }
                        
                        //添加行间隔色
                        if (opt.alternating){
                            methods.alternating.call($this);
                        }
                        
                        //添加货币标签currencyTag
                        if (opt.currencyTag){
                            methods.currencyTag.call($this, dataReturn.records);
                        }
                        //添加涨跌幅标签priceLimitTag
                        if (opt.priceLimitTag){
                            methods.priceLimitTag.call($this, dataReturn.records);
                        }
                        //分成两栏显示
                        if (opt.towColumns){
                            methods.towColumns.call($this);
                        }
                        //行滚动
                        if (opt.scroller && !opt.wrapAllowed){
                            methods.scroller.call($this);
                        }
                        //表头固定和列固定等
                        if (opt.fixedLayout && !noRrecords){
                            methods.fixedLayout.call($this);
                        }

                        // console.log('2--new-- ' + $state.state());
                        $state.resolve();
                        return $state.promise();
                    }

                    if (dType == 'html'){
                        //...
                        return;
                    }
                }

                function recordsUpdate(newField){
                    var $this = this;
                    var pairChange = $this.data('pairChange');
                    if (!!newField && (newField == pairChange)){
                        //console.log('#' + $this.attr('id') + ': 数据记录相同，更新单元格');
                        return true;
                    }else{
                        //console.log('#' + $this.attr('id') + ': 数据记录有变化，重建表格');
                        return false;
                    }
                }
            });
        },
        /**
         * 清空数据表，重置数据表结构
         */
        clearSheet: function(all){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');
                var allInit = (all === false) ? false : true;
                if (opt == undefined) {return;}

                _st = 0;
                _sl = 0;
                if (allInit){
                    if (opt.autoRefresh){
                        clearTimeout(clearTime.autoRefresh);
                        clearTime.autoRefresh = null;
                    }
                }
                //if (opt.fixedLayout){
                    methods.clearFixedLayout.call($this);
                //}
                //if (opt.towColumns){
                    $this.find('.san-sheet-col-1, .san-sheet-col-2').remove();
                    $this.find('.' + opt.sheetBody).removeClass('NONE');
                //}
                //if (opt.scroller){
                    clearInterval(clearTime.scroller);
                    clearTime.scroller = null;
                    $this.find('.san-sheet-scroller').remove();
                //}

                $this.find('.' + opt.sheetBody).find('tbody').empty();

                $this.attr('data-count', '');
                $this.attr('data-date', '');
                $this.attr('data-url', '');
                $this.data('pairChange', '');
            });
        },
        /**
         * 刷新
         */
        refresh: function(url){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');

                if (!opt) {return;}

                if (url) {
                    var newOpt = $.extend(opt, {'url': url});
                    $this.data('opt', newOpt);
                }
                methods.load.call($this);
                
                if (opt.mediaListening) {
                    $this.trigger(MEDIA_LISTENER + '.' + namespace);
                }
            });
        },
        resize: function(option) {
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    _opt = $.extend({}, opt),
                    rebuild = false;
                
                if (option && san.tools.type(option) === 'object') {
                    opt = $.extend({}, opt, option);
                    $this.data('opt', opt);
                }

                if (opt.wrapAllowed && !opt.scroller){
                    $this.find('.' + opt.sheetBody).addClass('san-sheet-wrap');
                } else {
                    $this.find('.' + opt.sheetBody).removeClass('san-sheet-wrap');
                }

                if (opt.towColumns && _opt.fixedLayout) {
                    methods.clearFixedLayout.call($this);
                    methods.towColumns.call($this);
                    
                    if (opt.callback && san.tools.type(opt.callback) === 'function') {
                        opt.callback.call($this);
                    }
                
                    if (V_VW < MEDIA_RULE.M) {
                        methods.suspendBarFilled.call($this);
                    } else {
                        methods.suspendBarDisabled.call($this);
                    }

                    return;
                }

                if (opt.fixedLayout) {
                    if (_opt.towColumns) {
                        $this.find('.san-sheet-col-1, .san-sheet-col-2').remove();
                        $this.find('.san-sheet').removeClass('NONE');
                    }
                    // _st = $this.find('.san-sheet-fixed-body').find('.' + opt.sheetBody).scrollTop();
                    // _sl = $this.find('.san-sheet-fixed-body').find('.' + opt.sheetBody).scrollLeft();
                    rebuild = true;
                    methods.clearFixedLayout.call($this);
                    methods.fixedLayout.call($this, rebuild);
                } else {
                    methods.clearFixedLayout.call($this);
                }

                if (opt.callback && san.tools.type(opt.callback) === 'function') {
                    opt.callback.call($this);
                }
                
                if (V_VW < MEDIA_RULE.M) {
                    methods.suspendBarFilled.call($this);
                } else {
                    methods.suspendBarDisabled.call($this);
                }

            });
        },
        loadFail: function(msg){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');   

                if (opt.autoRefresh){
                    methods.clearSheet.call($this, false);
                }else{
                    methods.clearSheet.call($this);
                }
                
                var $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)');

                if (opt.fixedLayout && opt.fixedLayoutType != 'header'){
                    var strBody = '<div class="san-sheet-fixed-body"></div>';
                    if ($this.find('.san-sheet-fixed-body').length == 0) $sheetBody.wrap(strBody);
                    var w = parseInt(opt.fixedBodyWidth, 10);
                    $sheetBody = $this.find('.san-sheet-fixed-body').find('.' + opt.sheetBody);
                    $sheetBody.css({
                        'overflow-y': 'hidden',
                        'overflow-x': 'auto'
                    }); //for ie9
                    if (w) $sheetBody.find('table').css('width', w + 'px');
                }

                //$sheetBody.append('<div class="' + opt.sheetFail + ' m-l-10 m-t-7 m-b-7 m-r-10">' + msg + '</div>');
                if (window.console) {console.log(msg);}
            });
        },
        /**
         * 添加行间隔色
         * this - 数据表sheet
         */
        alternating: function(){
            return this.each(function(){
                var $this = $(this),
                opt = $this.data('opt'); 

                $this.find('tbody').each(function(){
                    var $tbody = $(this);
                    //CSS3
                    $tbody.parent().addClass(opt.alternatingClass);
                    //ie8-
                    if (IE_V > 0 && IE_V <= 8){
                        $tbody.find('tr:nth-child(odd)').addClass('odd');
                        $tbody.find('tr:nth-child(even)').addClass('even');
                    }
                });
            });
        },
        /**
         * 添加行号
         * this - 数据表sheet
         */
        lineNumber: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)');
                
                //数据表table
                //复杂表头？ 待测试
                var $number = $sheetBody.find('thead').find('[data-sp=lineNumber]:eq(0)'),
                    i = $number.index();

                //插入列到指定位置
                $sheetBody.find('tbody').find('tr[data-row]').each(function(){
                    var $tr = $(this),
                        $td = $tr.children(':eq(' + i + ')'),
                        num = parseInt($tr.attr('data-row'), 10) + 1;
                    $td.attr('data-sp', 'lineNumber').text(num);
                });
            });
        },
        /**
         * 分栏显示(两栏)
         */
        towColumns: function(recover, callback){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)'),
                    $sheet1 = null,
                    $sheet2 = null;
                recover = recover === false ? true : false;

                if (recover) {
                    $this.removeClass('clearfix');
                    $this.find('.san-sheet-col-1, .san-sheet-col-2').addClass('NONE');//.remove();
                    $sheetBody.removeClass('NONE');
                    runCallback();
                    return;
                }

                if ($this.find('.san-sheet-col-1').length) {
                    $this.find('.san-sheet-col-1, .san-sheet-col-2').removeClass('NONE');
                    $sheetBody.addClass('NONE');
                    runCallback();
                    return;
                }

                $this.addClass('clearfix');
                $sheetBody.clone().insertAfter($sheetBody).addClass('san-sheet-col-1');
                $sheetBody.clone().insertAfter($sheetBody).addClass('san-sheet-col-2');
                $sheetBody.addClass('NONE');

                $sheet1 = $this.find('.san-sheet-col-1');
                $sheet2 = $this.find('.san-sheet-col-2');

                var len = $sheetBody.find('tbody').find('tr').length,
                    row = Math.round(len / 2);
                $sheet1.find('tbody').find('tr').each(function(i){
                    if (!opt.towColumnsAburton){
                        if (i > (row - 1)) {$(this).remove();}
                    }else{
                        if (!san.tools.isEven(i)) {$(this).remove();}
                    }
                });
                $sheet2.find('tbody').find('tr').each(function(i){
                    if (!opt.towColumnsAburton){
                        if (i < row) {$(this).remove();}
                    }else{
                        if (san.tools.isEven(i)) {$(this).remove();}
                    }
                    if (opt.towColumnsRowFill && i == len - 1 && len % 2 != 0){
                        var tdLen = $sheet1.find('tbody').find('tr:eq(0)').children().length;
                        $sheet2.find('tbody').append('<tr class="hover-none" data-row="' + len + '"><td colspan="' + tdLen + '">&nbsp;</td></tr>');
                    }
                });

                runCallback();

                function runCallback() {
                    if (san.tools.type(callback) == 'function') {
                        callback.call($this);
                    }
                }
                    
            });
        },
        /**
         * 货币标签（国旗图片）
         */
        currencyTag: function(data){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)');
                
                $sheetBody.find('thead').find('[data-tag="flag"]').each(function(){
                    var $obj = $(this),
                        target = $obj.attr('data-tag-target');

                    //获取手动索引值data-serial，如不存在获取元素索引值
                    var i = parseInt($obj.attr('data-serial'), 10) - 1;
                    if (i !== 0 && !i || i < 0) {i = $obj.index();}

                    var $td = null, pic = '', str = '';
                    $this.find('tbody').find('tr[data-row]').each(function(t){
                        $td = $(this).find('td:eq(' + i + ')');
                        // <img>结构
                        $td.attr('data-tag-target', target);
                        pic = data[t][target];
                        // '<span class="san-icon-flag-img m-r-10"><img ></span>'
                        str = '<div class="' + opt.currencyTagClass + '-img m-r-' + opt.currencyTagSpacing + '"><img src="' + pic + '"></div>';
                        $td.prepend(str);
                    });
                });
            });
        },
        /**
         * 涨跌幅标签
         */
        priceLimitTag: function(data){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)');
                
                var tag = [];
                $sheetBody.find('thead').find('[data-tag="priceLimit"]').each(function(d){
                    var $obj = $(this);
                    //获取手动索引值data-serial，如不存在获取元素索引值
                    var i = parseInt($obj.attr('data-serial'), 10) - 1;
                    if (!i || i <= 0) {i = $obj.index();}

                    // 涨跌幅标记组
                    tag.push({
                        // 所属单元格索引
                        'index': i,
                        // 取值来源
                        'target': ($obj.attr('data-tag-target') || $obj.attr('data-name')).split('/'),   // 显示位置
                        'position': $obj.attr('data-tag-position')
                    });
                });

                //遍历tbody各行
                $this.find('tbody').find('tr[data-row]').each(function(row){
                    var tagIndex = 0, tagLen = tag.length;
                    // 根据涨跌幅标记组遍历单元格
                    for (; tagIndex < tagLen; tagIndex++){
                        var $td = $(this).find('td:eq(' + tag[tagIndex]['index'] + ')');
                        var pos = tag[tagIndex]['position'];
                        var m = (pos == 'left') ? 'r' : 'l';  //默认左侧显示，补右边距

                        // 遍历取值源
                        var target = tag[tagIndex]['target'],
                            targetIndex = 0, targetLen = target.length,
                            targetValue = null,
                            sign = null,
                            str = '';

                        $td.attr({
                            'data-tag-target': target.join('/'),
                            'data-tag-position': pos
                        });

                        for (; targetIndex < targetLen; targetIndex++){
                            if (!data[row] || !target[targetIndex]) {continue;}
                            // 在data里寻找对应target
                            targetValue = data[row][target[targetIndex]];
                            // 涨跌幅判断标记
                            sign = methods.priceLimitJudge.call($this, targetValue);
                            // 插入
                            str = '<span class="' + opt.priceLimitTagClass[0] + ' m-' + m + '-' + opt.priceLimitTagSpacing +'" data-value-index="' + targetIndex + '"></span>';
                            (pos == 'right') ? $td.find('.' + opt.cellValue + '[data-value-index="' + targetIndex + '"]').after(str) : $td.find('.' + opt.cellValue + '[data-value-index="' + targetIndex + '"]').before(str);
                            // 更新标记状态
                            methods.priceLimitRefresh.call($this, $td, targetIndex, sign, opt.priceLimitTagClass);
                        }
                    }
                });
            });
        },
        /**
         * 涨跌幅标签标志位值的判断
         * 因数据不规范，标志位有各种类型的值，将其转为标准值并返回
         * 标志位的值： null、number（>0, 0, <0）、true/false、 string（true/false及数字）。其它类型数据不做处理
         * 标准值：1：表涨，-1：表跌，0：不做处理
         */
        priceLimitJudge: function(t){
            // null
            if (t == null) {return 0;}
            // boolean
            if (typeof t === 'boolean'){
                return t ? 1 : -1;
            }
            // string（仅true和false）
            // 字符串'0' 返回1？
            if (typeof t === 'string'){
                if ((t === 'true') || (parseFloat(t) >= 0)){
                    return 1;
                }else if ((t === 'false') || (parseFloat(t) < 0)){
                    return -1;
                }else{
                    return 0;
                }
            }
            // number
            // 数字0返回0？
            if (typeof t === 'number'){
                return (t > 0) ? 1 : (t < 0) ? -1 : 0;
            }
        },
        /**
         * 涨跌幅标签刷新
         * $td： jQuery对象，指定单元格
         * sign: 涨跌幅标志位的值（>, <, =0）
         * c: 一组表示涨跌幅的样式，opt.priceLimitTagClass。比如：
         *    ['san-icon', 'san-icon-up', 'san-icon-down', 'text-up', 'text-down']
         */
        priceLimitRefresh: function($td, index, sign, c){
            return this.each(function(){
                var opt = $(this).data('opt');
                var txtColor = (c[3] && c[4]) ? true : false;
                var $value = null,
                    $icon = null;

                $icon = $td.find('.' + c[0] + '[data-value-index="' + index + '"]');
                $value = $td.find('.' + opt.cellValue + '[data-value-index="' + index + '"]');
                if (sign > 0){
                    $icon.addClass(c[1] + ' ' + c[3]).removeClass(c[2] + ' ' + c[4]);
                    if (txtColor) {$value.addClass(c[3]).removeClass(c[4]);}
                }else if (sign < 0){
                    $icon.addClass(c[2] + ' ' + c[4]).removeClass(c[1] + ' ' + c[3]);
                    if (txtColor) {$value.addClass(c[4]).removeClass(c[3]);}
                }else{
                    $icon.removeClass(c[1] + ' ' + c[2] + ' ' + c[3] + ' ' + c[4]);
                    if (txtColor) {$value.removeClass(c[3] + ' ' + c[4]);}
                }
            });
        },
        /**
         * 行滚动（向上滚屏）
         * 约束：
         * 1. san-sheet-scroller需有固定height，并隐藏越界内容。
         * 2. 步进单位为行，每行的height需相等。
         * 3. 滚动行数+固定行数等于或超过总行数，不滚动。
         * 4. 不会重构表格间隔色，设置滚动参数时应注意间隔色重复的问题。
         * 5. 不能与下列功能同时使用：
         *    分两栏显示、表头固定、列固定
         * 生成结构：
         * <div san-sheet>
         *   <table></table>
         * </div>
         * <div san-sheet-scroller>
         *    <div san-sheet san-sheet-scroller-scroll>
         *       <table></table>
         *    </div>
         *    ...
         * </div>
         */
        scroller: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.find('.' + opt.sheetBody + ':eq(0)');

                if (opt.towColumns || opt.fixedLayout) return;

                //数据表格高和行高
                var sheetHeight = $sheetBody.innerHeight(),
                    trHeight = 0;
                //总记录数
                var len = $sheetBody.find('tbody').find('tr').length;
                //滚动行数
                var sl = parseInt(opt.scrollRows, 10) || len;
                //固定行数
                var fl = parseInt(opt.scrollFixedRows, 10) || 0;    
                if (sl + fl >= len) return;
                //滚动对象
                var $scrollBody = null;
                //每次滚动的高度
                var sh = 0;
                
                //生成san-sheet-scroller
                $this.append('<div class="san-sheet-scroller"></div>');
                $scrollBody = $this.find('.san-sheet-scroller');
                opt.alternating ? $scrollBody.attr('data-alternating', true) : $scrollBody.attr('data-alternating', false);
                var sheetBodyClass = $sheetBody.attr('class');
                var strTable = '';
                for (var i = 0; i < (len - fl); i++){
                    strTable += '<div class="' + sheetBodyClass + ' san-sheet-scroller-scroll"><table><tbody></tbody></table></div>';
                }
                $scrollBody.append(strTable);
                //补行
                var re = (len - fl) % sl;
                var tdLen = $sheetBody.find('tr:eq(0)').children().length;
                if (re != 0){
                    var strTd = '';
                    for (var i = 0; i < (sl - re); i++){
                        strTd = strTd + '<tr class="hover-none" data-row="' + len + '"><td colspan="' + tdLen + '"></td></tr>';
                    }
                    $scrollBody.append('<div class="' + sheetBodyClass + ' san-sheet-scroller-scroll"><table><tbody>' + strTd + '</tbody></table></div>');
                }
                $sheetBody.find('colgroup').clone().prependTo($scrollBody.find('table'));
                var sc = 0;
                $sheetBody.find('tbody').find('tr').each(function(i){
                    if (i == 0) trHeight = $(this).innerHeight();
                    if (i >= fl){
                        var $obj = $scrollBody.find('.san-sheet-scroller-scroll:eq(' + sc + ')');
                        $(this).appendTo($obj.find('table'));
                        sc++;
                    }
                });
                sh = trHeight * sl;
                $scrollBody.css('height', sh + 'px');

                if (opt.alternating){
                    $scrollBody.find('.san-sheet-scroller-scroll').each(function(){
                        var _alternating = $(this).find('tr').attr('data-row');
                        if (_alternating % 2 == 0){
                            $(this).addClass('san-sheet-scroller-scroll-odd');
                        }else{
                            $(this).addClass('san-sheet-scroller-scroll-even');
                        }
                    });
                }

                //设定最小间隔时间及最小持续时间
                var _scrollInterval = opt.scrollInterval >= 1000 ? opt.scrollInterval : 1000;
                var _scrollDuration = opt.scrollDuration <= opt.scrollInterval * 0.3 ? opt.scrollDuration : opt.scrollInterval * 0.3;
                clearTime.scroller = setInterval(function(){
                    var $first = $scrollBody.find('.san-sheet-scroller-scroll:eq(0)'),
                        _$first = $scrollBody.find('.san-sheet-scroller-scroll:lt(' + sl + ')');
                    $first.animate({
                        'margin-top': '-' + sh + 'px'
                    }, _scrollDuration, function(){
                        _$first.css('margin-top', 0).appendTo($scrollBody);
                    });
                }, opt.scrollInterval);
            });
        },
        /**
         * 固定结构布局
         * 约束：
         * 1. 包括表头固定（thead）、列固定（多列）、表头和列固定。
         * 2. 注意会改变HTML结构，详见各方法注释。
         * 3. 不能与下列功能同时使用：
         *    分两栏显示、行滚动
         */
        fixedLayout: function(build){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');
                   
                build = build === false ? false : true;

                //判断是否结构冲突，中断执行
                if (opt.towColumns || opt.scroller) {return;}

                //固定类型
                var fixedType = opt.fixedLayoutType;
                if (fixedType == 'header') {
                    methods.fixedHeader.call($this, build);
                }else if (fixedType == 'column') {
                    methods.fixedColumn.call($this, build);
                }else if (fixedType == 'all') {
                    methods.fixedDouble.call($this, build);
                }

                //绑定滚动事件
                var $body = $this.find('.san-sheet-fixed-body'),
                    $sheet = $body.find('.' + opt.sheetBody),
                    $fixedHead = $body.prev('.san-sheet-fixed-head'),
                    $fixedColumn = $body.next('.san-sheet-fixed-column');
                $sheet.off('scroll.sanDatasheet').on('scroll.sanDatasheet', function(){
                    var st = $sheet.scrollTop(),
                        sl = $sheet.scrollLeft();

                    if ($fixedHead.length) {$fixedHead.find('.' + opt.sheetBody).scrollLeft(sl);}
                    if ($fixedColumn.length) {$fixedColumn.scrollTop(st);}
                    
                    var $bar = $('body').children('#suspend-bar-' + opt.sheetId),
                        $barHead = null,
                        $barBody = null;
                    if ($bar.attr('data-status') !== 'enabled') { return; }
                    $barHead = $bar.find('.san-sheet-fixed-head').find('.' + opt.sheetBody);
                    $barBody = $bar.find('.san-sheet-fixed-body').find('.' + opt.sheetBody);
                    if ($barHead.length) { $barHead[0].scrollTo(sl, st); }
                    if ($barBody.length) { $barBody[0].scrollTo(sl, st); }
                    $barHead = null;
                    $barBody = null;
                });
            });
        },
        clearFixedLayout: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');

                // 删除各固定元素
                $this.find('.san-sheet-fixed-head').remove();
                $this.find('.san-sheet-fixed-column').remove();
                $this.find('.san-sheet-fixed-cross').remove();
                // 删除san-sheet-fixed-body
                var $fixedBody = $this.find('.san-sheet-fixed-body');
                if ($fixedBody.length){
                    $fixedBody.find('thead').removeClass('NONE');
                    $fixedBody.find('table').removeAttr('style');
                    $fixedBody.find('tr').each(function(){
                        $(this).children(':eq(0)').removeAttr('style');
                    });
                    $fixedBody.find('.' + opt.sheetBody).removeAttr('style').unwrap();
                }

                // $this.find('.san-sheet-col-1, .san-sheet-col-2').remove();
                // $this.children('.san-sheet').removeClass('NONE');
            });
        },
        /**
         * 表头固定
         * 约束：
         * 1.要看到表头固定，san-sheet-fixed-body中的san-sheet应有一个固定height，并且小于其内部table的height。
         * 2.san-sheet-fixed-body中table的thead隐藏不显示。
         * 3.san-sheet-fixed-head中需要有一个预留位置，用于和san-sheet-fixed-body中有垂直滚动条时对齐。
         * 生成结构：
         * ...
         * <div san-sheet-fixed-head>
         *   <div san-sheet><table><thead>...</thead></table></div>
         * </div>
         * <div san-sheet-fixed-body>
         *   <div san-sheet><table><tbody>...</tbody></table></div>
         * </div>
         * ...
         */
        fixedHeader: function(build){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');

                build = build === false ? false : true;

                //更新HTML结构
                var $sheetBody = $this.children('.' + opt.sheetBody + ':eq(0)');
                var strHead = '<div class="san-sheet-fixed-head"></div>',
                    strBody = '<div class="san-sheet-fixed-body"></div>';
                if (!$this.find('.san-sheet-fixed-head').length) {$sheetBody.before(strHead);}
                if (!$this.find('.san-sheet-fixed-body').length) {$sheetBody.wrap(strBody);}
                var $fixedHead = $this.find('.san-sheet-fixed-head'),
                    $fixedBody = $this.find('.san-sheet-fixed-body');
                $sheetBody = $fixedBody.find('.' + opt.sheetBody);
                $sheetBody.removeClass('OA');
                
                $sheetBody.css('height', '');

                if (build) {
                    $sheetBody.find('thead').removeClass('NONE');
                    //创建固定表头
                    var $clone = $sheetBody.clone();
                    $clone.find('tbody').remove();
                    $fixedHead.empty().html($clone);
                    $clone = null;
                    $sheetBody.find('thead').addClass('NONE');
                    
                    //设置指定的width
                    var w = parseInt(opt.fixedBodyWidth, 10) || parseInt(opt.width, 10);
                    if (w){
                        $sheetBody.find('table').css('width', w + 'px');
                        $fixedHead.find('table').css('width', w + 'px');
                    }
                }
               
                var containerWidth = $this.width();

                var h = parseInt(opt.fixedBodyHeight, 10);
                if (h){
                    (containerWidth < w) ? $sheetBody.css('height', h + SSZ + 'px') : $sheetBody.css('height', h + 'px');

                    if (h < $sheetBody.find('table').find('tbody').height()){
                        $fixedHead.css('padding-right', SSZ + 'px');
                    }
                }
            });
        },
        /**
         * 列固定
         * 约束：
         * 1.要看到列固定，san-sheet-fixed-body中的table应有一个固定width，并且大于显示区域。
         * 2.san-sheet-fixed-column使用绝对定位。
         * 3.可多列固定，但注意固定列的width之和应小于显示区域。
         * 生成结构：
         * ...
         * <div san-sheet-fixed-body>
         *   <div san-sheet><table>...</table></div>
         * </div>
         * <div san-sheet-fixed-column>
         *   <div san-sheet><table>...</table></div>
         * </div>
         * ...
         */
        fixedColumn: function(build){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.children('.' + opt.sheetBody + ':eq(0)'),
                    fixedColNumber = opt.fixedColNumber;
                
                build = build === false ? false : true;
                //更新HTML结构
                var strColumn = '<div class="san-sheet-fixed-column"></div>',
                    strBody = '<div class="san-sheet-fixed-body"></div>';
                if ($this.find('.san-sheet-fixed-column').length == 0) {$sheetBody.after(strColumn);}
                if ($this.find('.san-sheet-fixed-body').length == 0) {$sheetBody.wrap(strBody);}
                var $fixedColumn = $this.find('.san-sheet-fixed-column'),
                    $fixedBody = $this.find('.san-sheet-fixed-body');
                $sheetBody = $fixedBody.find('.' + opt.sheetBody);
                $sheetBody.removeClass('OA');
                $sheetBody.css('height', '');//.find('thead').removeClass('NONE');
                
                if (build) {
                    //创建固定列
                    var $clone = $sheetBody.clone();
                    $clone.find('colgroup').remove();
                    var _i = 0, rowspan = 0, a = 0;
                    $clone.find('tr').each(function(i){
                        var $tr = $(this);
                        $tr.children().each(function(i){
                            var $td = $(this);
                            if (i >= fixedColNumber) {return false;}
                            if ($td.attr('rowspan')) {
                                _i++;
                                rowspan = parseInt($td.attr('rowspan')) - 1;
                            }
                        });
                        
                        if (!a) {
                            $tr.children().slice(opt.fixedColNumber).remove();
                        } else {
                            $tr.children().slice(opt.fixedColNumber - _i).remove();
                        }
                        if (rowspan <= 0) {
                            a = 0;
                            _i = 0;
                        } else {
                            a = 1;
                        }
                        rowspan--;
                        // $(this).children().slice(opt.fixedColNumber).remove();
                    });
                    var $tr = $clone.find('thead>tr'), redun = false;
                    if ($tr.length > 1) {
                        $tr.each(function(){
                            var $this = $(this);
                            if (redun) {
                                $this.remove();
                                return;
                            }
                            if (!$this.children('[colspan]').length) {
                                redun = true;
                            }
                        });
                    }
                    $fixedColumn.empty().html($clone);
                    $tr = null;
                    redun = false;
                    $clone = null;
                }

                //设置数据表格尺寸
                // var containerWidth = $this.closest('.' + opt.sheet).width();
                var containerWidth = $this.width();
                var trH = $sheetBody.find('thead').find('td:eq(0)').outerHeight();
                var w = parseInt(opt.fixedBodyWidth, 10) || parseInt(opt.width, 10),
                    h = parseInt(opt.fixedBodyHeight, 10);
                h = h + trH + 0;    // +表头

                if (w){
                    $sheetBody.find('table').css('width', w + 'px');
                }
                if (h){
                    (containerWidth < w) ? $sheetBody.css('height', h + SSZ + 'px') : $sheetBody.css('height', h + 'px');
                }
                
                if (_sl || _st) {
                    $sheetBody[0].scrollTo(_sl, _st);
                }
                
                //固定列定位
                var p = $sheetBody.position();
                $fixedColumn.css({
                    'top': p.top + 'px',
                    'left': p.left + 'px'
                });

                //设置固定列尺寸
                $fixedColumn.find('table').css('width', 'auto').find('thead').find('td:eq(0)').css('height', trH);

                $sheetBody.find('tr').each(function(i){
                    var $tr = $(this);
                    var $td1 = $tr.children(':eq(0)');
                    var h1 = '';

                    $td1.css('height', '');
                    h1 = $td1.outerHeight();
                    $td1.css('height', h1 + 'px');

                    if (i == 0){
                        var colTableWidth = 0;
                        $tr.children().each(function(_i){
                            if (_i <= (fixedColNumber - 1)){
                                // var colWidth = $(this).outerWidth() - pr;
                                // var colWidth = $(this).width();
                                var colWidth = $(this).innerWidth();
                                colTableWidth = colTableWidth + colWidth;
                                $fixedColumn.find('tr:eq(0)').children('*:eq(' + _i + ')').css('width', colWidth + 'px');
                            }
                        });
                        $fixedColumn.find('table').css('width', colTableWidth);
                    }
                    $fixedColumn.find('tr:eq(' + i + ')').children(':eq(0)').css('height', h1 + 'px');
                });
                $fixedColumn.css('height', $sheetBody[0].clientHeight + 'px');
            });
        },
        /**
         * 表头及列固定
         * 约束：
         * 1.注意，在san-sheet-fixed-body中，width设置在table上和height设置在san-sheet。
         * 2.其它详见表头固定和列固定的注释。
         * 生成结构：
         * ...
         * <div san-sheet-fixed-head>
         *   <div san-sheet><table><thead>...</thead></table></div>
         * </div>
         * <div san-sheet-fixed-body>
         *   <div san-sheet><table>...</table></div>
         * </div>
         * <div san-sheet-fixed-column>
         *   <div san-sheet><table>...</table></div>
         * </div>
         * <div san-sheet-fixed-cross>
         *   <div san-sheet><table>.../table></div>
         * </div>
         * ...
         */
        fixedDouble: function(build){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $sheetBody = $this.children('.' + opt.sheetBody + ':eq(0)'),
                    fixedColNumber = opt.fixedColNumber;
                
                build = build === false ? false : true;

                //更新HTML结构
                var strHead = '<div class="san-sheet-fixed-head"></div>',
                    strColumn = '<div class="san-sheet-fixed-column"></div>',
                    strBody = '<div class="san-sheet-fixed-body"></div>',
                    strCross = '<div class="san-sheet-fixed-cross"></div>';
                
                if ($this.find('.san-sheet-fixed-head').length == 0) {$sheetBody.before(strHead);}
                if ($this.find('.san-sheet-fixed-column').length == 0) {$sheetBody.after(strColumn);}
                if ($this.find('.san-sheet-fixed-body').length == 0) {$sheetBody.wrap(strBody);}

                var $fixedHead = $this.find('.san-sheet-fixed-head'),
                    $fixedColumn = $this.find('.san-sheet-fixed-column'),
                    $fixedBody = $this.find('.san-sheet-fixed-body');
                $sheetBody = $fixedBody.find('.' + opt.sheetBody);
                $sheetBody.removeClass('OA');

                $sheetBody.css('height', '').find('thead').removeClass('NONE');

                if (build) {
                    //创建固定表头、固定列
                    var $cloneHead = $sheetBody.clone(),
                        $cloneColumn = $sheetBody.clone();

                    $cloneHead.find('tbody').remove();
                    $fixedHead.empty().html($cloneHead);
                    $cloneHead = null;
                    
                    $cloneColumn.find('colgroup').remove();
                    var _i = 0, rowspan = 0, a = 0;
                    $cloneColumn.find('tr').each(function(i){
                        var $tr = $(this);
                        $tr.children().each(function(i){
                            var $td = $(this);
                            if (i >= fixedColNumber) {return false;}
                            if ($td.attr('rowspan')) {
                                _i++;
                                rowspan = parseInt($td.attr('rowspan')) - 1;
                            }
                        });
                        if (!a) {
                            $tr.children().slice(opt.fixedColNumber).remove();
                        } else {
                            $tr.children().slice(opt.fixedColNumber - _i).remove();
                        }
                        if (rowspan <= 0) {
                            a = 0;
                            _i = 0;
                        } else {
                            a = 1;
                        }
                        rowspan--;
                        // $(this).children().slice(opt.fixedColNumber).remove();
                    });
                    var $tr = $cloneColumn.find('thead>tr'), redun = false;
                    if ($tr.length > 1) {
                        $tr.each(function(){
                            var $this = $(this);
                            if (redun) {
                                $this.remove();
                                return;
                            }
                            if (!$this.children('[colspan]').length) {
                                redun = true;
                            }
                        });
                    }
                    $fixedColumn.empty().html($cloneColumn);
                    $tr = null;
                    redun = false;
                    $cloneColumn = null;
                }

                //设置数据表格尺寸
                // var containerWidth = $this.closest('.' + opt.sheet).width();
                var containerWidth = $this.width();
                var w = parseFloat(opt.fixedBodyWidth, 10) || parseInt(opt.width, 10),
                    h = parseFloat(opt.fixedBodyHeight, 10);

                if (w){
                    $sheetBody.find('table').css('width', w + 'px');
                    $fixedHead.find('table').css('width', w + 'px');
                }
                if (h){
                    (containerWidth < w) ? $sheetBody.css('height', h + SSZ + 'px') : $sheetBody.css('height', h + 'px');
                }

                // 设置固定表头
                if (h < $sheetBody.find('table').find('tbody').height()){
                    $fixedHead.css('padding-right', SSZ + 'px');
                }
                
                if (_sl || _st) {
                    $sheetBody[0].scrollTo(_sl, _st);
                    $fixedHead.find('.' + opt.sheetBody).scrollTo(_sl, _st);
                }

                //固定列定位
                var ph = $fixedHead.position();
                $fixedColumn.css({
                    'top': ph.top + 'px',
                    'left': ph.left + 'px'
                });

                //设置固定列尺寸
                var tWidth = 0;
                $sheetBody.find('tr').each(function(i){
                    var $tr = $(this);
                    var $td1 = $tr.children(':eq(0)');
                    var h1 = '';

                    $td1.css('height', '');
                    h1 = $td1.outerHeight();
                    $td1.css('height', h1 + 'px');

                    if (i == 0){
                        var colTableWidth = 0
                        $tr.children().each(function(_i){
                            if (_i <= (opt.fixedColNumber - 1)){
                                // var colWidth = $(this).outerWidth() - pr;
                                // var colWidth = $(this).width();
                                var colWidth = $(this).innerWidth();
                                tWidth = tWidth + colWidth;
                                $fixedColumn.find('tr:eq(0)').children('*:eq(' + _i + ')').css('width', colWidth + 'px');
                            }
                        });
                        $fixedHead.find('tr:eq(' + i + ')').children(':eq(0)').css('height', h1 + 'px');
                    }
                    $fixedColumn.find('tr:eq(' + i + ')').children(':eq(0)').css('height', h1 + 'px');
                });

                $sheetBody.find('thead').addClass('NONE');  //important，需放在此处执行，否则获取不到正确宽度
                // $sheetBody.find('thead').remove();
                $fixedColumn.find('table').css('width', tWidth + 'px');
                $fixedColumn.css('height', $fixedHead.find('td:eq(0)')[0].clientHeight + $sheetBody[0].clientHeight + 'px');

                // 创建交叉区域
                if ($this.find('.san-sheet-fixed-cross').length == 0) $fixedColumn.after(strCross);
                var $fixedCross = $this.find('.san-sheet-fixed-cross'),
                    $cloneCross = null;
                if (build) {
                    $cloneCross = $fixedHead.find('.' + opt.sheetBody).clone();
                    $cloneCross.find('colgroup').remove();
                    $cloneCross.find('tr:eq(0)').children().slice(opt.fixedColNumber).remove();
                    $fixedCross.empty().html($cloneCross);
                    $cloneCross = null;
                }

                // 交叉区域定位
                $fixedCross.css({
                    'top': ph.top + 'px',
                    'left': ph.left + 'px'
                }).find('table').css('width', tWidth + 'px');
                // 设置交叉区域尺寸
                $fixedHead.find('tr:eq(0)').children().each(function(i){
                    if (i <= (opt.fixedColNumber - 1)){
                        var $td = $(this);
                        var $crossTd = $fixedCross.find('tr:eq(0)').children('*:eq(' + i + ')');
                        if (i == 0) {$crossTd.css('height', parseInt($td.css('height'), 10) + 'px')}
                        // var colWidth = $(this).outerWidth() - pr;
                        // var colWidth = $(this).width();
                        var colWidth = $td.innerWidth();
                        $crossTd.css('width', colWidth + 'px');
                    }
                });
            });
        },
        suspendBar: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    offsetTop = 0,
                    sheetRect, sheetTop,sheetBottom,
                    headHeight,
                    $bar = null;

                if (V_VW >= MEDIA_RULE.M || opt.scroller) { return; }
                
                offsetTop = $('#main-page-head').length ? $('#main-page-head').outerHeight() : 0;

                var filled = methods.suspendBarFilled.call($this, true);
                $bar = filled.content;
                headHeight = filled.headHeight;

                $bar.css({
                    'top': offsetTop + 'px'
                })

                $this.off('suspendScroll').on('suspendScroll.' + namespace, function(){
                    var _$this = $(this);
                    sheetRect = _$this[0].getBoundingClientRect();
                    sheetTop = sheetRect.top;
                    sheetBottom = sheetRect.bottom;

                    if (sheetTop < offsetTop && sheetBottom > offsetTop + headHeight) {
                        methods.suspendBarEnabled.call($this, $bar);
                    } else {
                        methods.suspendBarDisabled.call($this, $bar);
                    }
                }).trigger('suspendScroll.' + namespace);
            });
        },
        suspendBarFilled: function(ref){
            var $this = $(this),
                opt = $this.data('opt'),
                sheetId = opt.sheetId,
                $sheet = null,
                $head = null,
                $bar = null,
                $clone = null;

            $bar = $('#suspend-bar-' + sheetId);
            if (!$bar.length) {
                $('body').append('<div class="san-datasheet-suspend-bar" id="suspend-bar-' + sheetId + '"></div>');
                $bar = $('#suspend-bar-' + sheetId);
            }

            if (!opt.fixedLayout && !opt.towColumns) {
                $sheet = $this.find('.' + opt.sheetBody);
                $head = $sheet.find('thead');
            }

            if (opt.towColumns) {
                $sheet = $this.children(':eq(0)');
                $head = $sheet.find('thead');
            }

            if (opt.fixedLayout && opt.fixedLayoutType === 'header') {
                $sheet = $this.children(':eq(0)');
                $head = $sheet.find('thead');
            }

            if (opt.fixedLayout && opt.fixedLayoutType === 'column') {
                $sheet = $this.children();
                $head = $this.children(':eq(0)').find('thead');
            }

            if (opt.fixedLayout && opt.fixedLayoutType === 'all') {
                $sheet = $this.children();
                $head = $this.children(':eq(0)').find('thead');
            }

            $clone = $sheet.clone();
            $clone.find('tbody').remove();
            $clone.css('height', '');
            if (opt.fixedLayout && opt.fixedLayoutType === 'all') {
                $clone.find('.' + opt.sheetBody).css('height', '');
            }
            
            $bar.html($clone);
            if (ref) {
                return {
                    'content': $bar,
                    'headHeight': $head.height()
                }
            }

        },
        suspendBarEnabled: function($bar){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt'),
                    $body = $this.find('.san-sheet-fixed-body'),
                    $sheet = $body.find('.' + opt.sheetBody);
                
                if (!$bar || $bar.length == 0) {
                    $bar = $('#suspend-bar-' + opt.sheetId);
                }
                $bar.attr('data-status', 'enabled');

                var st = $sheet.scrollTop(),
                    sl = $sheet.scrollLeft(),
                    $barHead = $bar.find('.san-sheet-fixed-head').find('.' + opt.sheetBody),
                    $barBody = $bar.find('.san-sheet-fixed-body').find('.' + opt.sheetBody);
                if ($barHead.length) { $barHead[0].scrollTo(sl, st); }
                if ($barBody.length) { $barBody[0].scrollTo(sl, st); }
            });
        },
        suspendBarDisabled: function($bar){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');

                if (!$bar || $bar.length == 0) {
                    $bar = $('#suspend-bar-' + opt.sheetId);
                }
                $bar.attr('data-status', 'disabled');
            });
        },
        suspendBarRemove: function($bar){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('opt');
                
                delete SCROLL_LISTENER_GROUP[opt.sheetId];

                if (!$bar || $bar.length == 0) {
                    $bar = $('#suspend-bar-' + opt.sheetId);
                }
                $bar.remove();
            });
        }
    };

    $.fn.sanDatasheet = function(){
        var datasheet = san.tools.objectCreate(san.widget);
        return datasheet.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanDatasheet数据提取范例
 * 这只是一个数据提取范例。该范例只进行了简单数据处理，提取要显示的数据，如有必要进行拼合等。并不适用于所有使用场景。
 * 要提取的数据，其位置，名称，格式等在各json文件中均不相同，应根据页面实际情况自行处理。
 * 参数：
 * $sheet - 当前的数据表格jQuery对象
 * data - 来自json，要进行提取的数据
 * date - 日期
 * records - 数据记录
 * count - 要提取的数据记录条数。记录数不足时将补空行。
 * delimiter - 一个单元格内多个值之间的分隔符。默认'/'。
 * toSplice - true（默认） || false。设为false，不拼接数据，将把该组数据组合成数组。
 *            true时，拼合数据，返回一个字符串。
 *            false时，不拼合数据，返回一个数组。
 */
var _example_dataFormatter = function($sheet, date, records, count, delimiter, toSplice){
    //对应数据项
    var field = $sheet.data('field'),
        fieldPlus = $sheet.data('fieldPlus');
    var aData = [],
        dataCount = 0;
    var count = (typeof count == 'number' && count > 0) ? count : 0;
    var _toSplice = (toSplice === false) ? false : true;

    //记录值
    $.each(records, function(n, v){
        aData[n] = [];
        var i = 0, len = field.length;
        for (; i < len; i++){
            if (field[i].length > 1){
                var j = 0, l = field[i].length;
                if (_toSplice){
                    // 多个值拼接
                    aData[n][i] = '';
                    for (; j < l; j++){
                        aData[n][i] += san.tools.trim(v[field[i][j]]);
                        // 使用'{/}'拼接
                        if ((j + 1) < l) aData[n][i] += '{' + (delimiter || '/') + '}';
                    }
                }else{
                    // 不拼接，生成数组
                    aData[n][i] = [];
                    for (; j < l; j++){
                        aData[n][i].push(san.tools.trim(v[field[i][j]]));
                    }
                }
            }else{
                aData[n].push(san.tools.trim(v[field[i]]));
            }
        }
        dataCount = n + 1;
        if (dataCount == count) {return false;}
    });

    if (dataCount < count){
        var _i = dataCount, _len = count;
        for (; _i < _len; _i++){
            aData[_i] = [];
            var i = 0, len = field.length;
            for (; i < len; i++){
                aData[_i].push('');
            }
        }
    }

    return {
        'records': records,
        'newData': aData, 
        'count': dataCount, 
        'date': san.tools.trim(date)
    };
}



/**
 * sanDatasheet数据提取范例 2
 * 参数：
 * $sheet - 当前的数据表格jQuery对象
 * date - json中的要展示的日期
 * records - json中要展示的数据记录。即json结构范例中的"records"。
 * listName - records中的列表。即json结构范例中的"interestRateSwapList"。
 * json结构范例：
 * 该范例适用于以下json数据结构：
    "records":[{
        "refRate":"FR007",
        "refRateEN":"FR007",
        "interestRateSwapList":[{...},{...},...],
        "totalFixRate":45.0
    },{...},...]
 * 1.该表格记录总数是有效数据行数（非空行）
 * 2.如果需要合并单元格，为一组要合并的单元格添加自定义属性data-merge="{NAME}"。不同组使用不同的{NAME}。在回调方法内执行mergeCell()。
 */
var _example_dataFormatter_2 = function($sheet, date, records, listName){
    var field = $sheet.data('field');
    var aData = [], dataCount = 0;
    $.each(records, function(n, v){
        var f, flen = field.length;
        var a = [];
        var i = 0, len = v[listName].length;
        for(; i < len; i++){
            a[i] = [];
            for(f = 0; f < flen; f++){
                var _field = String(field[f]).split('@');
                var _flen = _field.length;
                if (_flen > 1){
                    a[i].push(v[_field[1]][i][_field[0]]);
                }else{
                    a[i].push(v[_field[0]]);
                }
            }
            aData.push(a[i]);
        }
    });
    return {
        'records': records,
        'newData': aData, 
        'count': aData.length, 
        'date': $.trim(date)
    };
}



/**
 * 数据记录处理范例： 合并单元格
 * 根据thead中data-merge的索引位置，合并tbody中同列且具有相同data-merge值的单元格。
 * 注意：会导致同列不相邻的具有相同data-merge值的单元格被删除。
 */
function mergeCell($sheet, alternating){
    $sheet.find('thead').find('[data-merge]').each(function(){
        var v = $(this).attr('data-merge'),
            i = $(this).index();
        $sheet.find('tbody').find('tr').each(function(){
            $(this).children('*:eq(' + i + ')').attr('data-merge', v);
        });
        var n = 1, alt = 1;
        $sheet.find('tbody').find('tr').each(function(){
            var $tr = $(this);
            var $td = $tr.find('[data-merge="' + v + '"]');

            if ($td.length == 0){return;}
            
            var value = $td.attr('data-value');

            if (alternating === true){
                if (san.tools.isEven(alt)){
                    $td.addClass('bg-sp-2');
                }else{
                    $td.addClass('bg-sp-1');
                }
            }

            $td.parent().nextAll().each(function(i){
                var $td2 = $(this).find('[data-merge="' + v + '"]'),
                    _value = $td2.attr('data-value');

                if (_value == value){
                    $td2.next().addClass('cell-merge-next');
                    $td2.remove();
                    $td.attr('rowspan', ++n);
                }else{
                    n = 1;
                    alt++;
                    return false;
                }
            });
        });
    });
}



/**
 * 两栏数据表格附加：相同索引行等高显示
 * 必要条件：数据表格允许多行显示
 */
function towColumnsPlus($obj){
    var $t1 = $obj.find('.san-sheet-col-1'),
        $t2 = $obj.find('.san-sheet-col-2');
    
    if (!$t1.hasClass('san-sheet-wrap')) {$t1.addClass('san-sheet-wrap');}
    if (!$t2.hasClass('san-sheet-wrap')) {$t2.addClass('san-sheet-wrap');}

    var $td1 = null, $td2 = null,
        index = 0, 
        h1 = null, h2 =null, h = null;
    $t1.find('tr[data-row]').each(function(){
        $td1 = $(this).find('td:eq(0)');
        $td1.css('height', '');
        index = $(this).index();
        $td2 = $t2.find('tbody').find('tr:eq(' + index + ')').find('td:eq(0)');
        $td2.css('height', '');
        h1 = $td1.outerHeight(true);
        h2 = $td2.outerHeight(true);
        if (h1 != h2){
            h = Math.max(h1, h2);
            $td1.css('height', h + 'px');
            $td2.css('height', h + 'px');
        }
    });
}



/*
 * 定义数据数据表格的宽度方案
 * 注：此方法适用需要计算table宽度的场景，%的列宽分配方案无需调用此方法
 * 参数：
 * $sheet：数据表格，jQeruy对象
 * w：数组，各列宽，单位px
 * 返回值：
 * width：表格宽度
 * colWidth：各列宽
 * colHtml：用于设定列宽的html代码（<col>）
 */
function getsheetWidthCase($sheet, w) {
    var $tr, trLen, strCol = '',
        rw = 0, i, len,
        dif,
        multiHead,
        scroll;
    if (!$sheet.length || !w) {return false;}
    if ($sheet.find('.san-sheet-fixed-body').length){
        scroll = $sheet.width() >= $sheet.find('.san-sheet-fixed-body').find('table').outerWidth() ? 0 : SSZ;
    } else {
        scroll = $sheet.width() >= $sheet.find('table:eq(0)').outerWidth() ? 0 : SSZ;
    }
    multiHead =$sheet.find('thead:eq(0)').find('tr').length > 1 ? true : false;
    if (multiHead) {
        $tr = $sheet.find('thead:eq(0)>tr').children('[data-serial]');
    } else {
        $tr = $sheet.find('thead:eq(0)>tr').children();
    }
    trLen = $tr.length;
    len = w.length;
    for (i = 0; i < len; i++) {
        strCol += '<col width="' + w[i] +'" />';
        rw += w[i];
    }
    var b = V_VW < MEDIA_RULE.M ? V_VW - scroll : $sheet.outerWidth() - scroll;
    if (rw < b) {
        dif = Math.floor((b - rw) / trLen);
        rw = 0;
        strCol = '';
        for (i = 0; i < len; i++) {
            if (i != len - 1) {
                w[i] += dif;
                strCol += '<col width="' + w[i] +'" />';
            } else {
                w[i] = b - rw;
                strCol += '<col width="*" />';
            }
            // strCol += '<col width="' + w[i] +'" />';
            rw += w[i];
        }
    }
    // 修正实际宽度不是整数的情况
    if ($sheet.outerWidth() != san.view.rect($sheet[0]).width) {
        rw++;
    }
    return {
        'width': rw,
        'colWidth': w,
        'colHtml': strCol
    };
}



/*
 * 年份下拉选择框设置
 * 参数：
 * yearId, monthId - 年/月下拉选择框id
 * data - 年月数据，年月名值对的对象或json字符串
 * current - 选中项，数组[year, month]或字符串'year-month'
 */
function jsonYearSelect(yearId, monthId, data, current){
    var y = '', m = '';
    if (typeof data == 'string'){ data = $.parseJSON(data); }
    if (typeof current == 'string'){ current = current.split('-'); }
    $.each(data, function(n, v){
        var selected = '';
        if (n == current[0]) {selected = 'selected';}
        y = '<option value="' + n + '" ' + selected +'>' + n + '</option>' + y;
    });
    $('#' + yearId).html(y);

    jsonMonthSelect(monthId, data, current);
}



/*
 * 月份下拉选择框设置
 * 参数：
 * monthId - 年/月下拉选择框id
 * data - 年月数据，年月名值对的对象或json字符串
 *        比如：{"2017":"06,05,04,03,02,01"}或"{\"2017\":\"06,05,04,03,02,01\"}"
 * current - 选中项，数组[year, month]或字符串'year-month'
 */
function jsonMonthSelect(monthId, data, current){
    if (typeof data == 'string'){ data = $.parseJSON(data); }
    if (typeof current == 'string'){ current = current.split('-'); }
    var m = '', a = data[current[0]].split(','), i, len = a.length;
    var selected = 0;
    for (i = 0; i < len; i++){
        if (current[1] == parseInt(a[i], 10)){selected = i;}
        m += '<option value="' + a[i] + '">' + a[i] + '</option>';
        // m += '<option value="' + parseInt(a[i], 10) + '">' + a[i] + '</option>';
    }
    var $month = $('#' + monthId);
    $month.html(m).find('option:eq(' + selected + ')').prop('selected', true);
}



/**
 * 返回<option>字符串
 * @author: zhxming
 * 两种形式：
 * jSelectOption(data, selected, arrValue)
 * jSelectOption(data, text, value, selected)
 * 第一种形式适用于data是普通数组。注意，第二个参数必须是Number。
 * 第二种形式适用于data是对象数组。注意，第二个参数必须是String。
 * value或arrValue不存在时，<option>的value值等于其显示文本。
 * 参数：
 * data - Array，普通数组或对象数组。包含一组组成option各要素的对象。
 * text - String，对象属性名，<option>要显示内容
 * value - String，对象属性名，<option>的value值
 * arrValue - Array，普通数组，对应于data，存放<option>的value值。
 * selected - Number || String，默认选中项，数字（从1起始的索引号） || value值。默认1。<0倒数。
 *            注意，如果是value值，必须转成String型再传入，防止与Number混淆。
 */
function jSelectOption(data, arg2, arg3, arg4){
    if (!data) { return false; }
    var option = '';
    var i, len = data.length;
    var ss = null, si = null;

    if (arg2 && typeof arg2 !== 'number'){
        if (typeof arg4 == 'string'){
            ss = arg4;
        }else{
            si = parseInt(arg4, 10) || 1;
            if (si < 0) { si = (len + 1) + si; }
        }
        for (i = 0; i < len; i++) {
            var t = data[i][arg2], v = t, sel = '';
            //mbl update
            if (arg3) { v = data[i][arg3]; }
            if ((ss && v == ss) || (i == (si - 1))){
                sel = ' selected';
            }
            option += '<option value="' + v + '"' + sel + '>' + t + '</option>';
        }
    }

    if (typeof arg2 === 'undefined') { arg2 = 1; }

    if (typeof arg2 === 'number'){
        (arg2 >= 0) ? si = (arg2 || 1) : si = (len + 1) + arg2;
        for (i = 0; i < len; i++) {
            var t = data[i], v = t, sel = '';
            if (i == (si - 1)){
                sel = ' selected';
            }
            if (arg3) { v = arg3[i]; }
            option += '<option value="' + v + '"' + sel + '>' + t + '</option>';
        }
    }

    return option;
}



/**
 * getUTC()
 * 获取指定显示格式的日期字符串
 * @author: zhxming
 * 约束：
 * 1.传入的日期字符串需时标准格式的日期字符串，非标准格式的字符串在不同浏览器下Date()的解析结果不同。
 * 标准日期格式如下：
 * 2016/04/30 14:07:54, 04/30/2016, April 30 2016, 30 Apr 2016
 * 2.传入参数会默认判定为String，如果传入的是一串数字，需要先使用parseInt()转换格式
 */
var getUTC = function(option) {
    var opt = $.extend({
        //日期字符串，空值表示当天
        date: null,
        /* 返回的日期字符串的显示格式
         * YYYY, YYY, YY, Y - 年。如2016
         * MM - 月。<10的补0，如05，12
         * M - 月。 不补0
         * MMMM - 月。 英文。如January
         * MMM - 月。英文简写。如Jan
         * DD - 日。<10的补0
         * D - 日。
         * WW - 星期。英文。如Sunday
         * W - 星期。英文简写。如Sun
         * hh - 小时。<10的补0
         * h - 小时。
         * mm - 分。<10的补0
         * m - 分。
         * ss - 秒。<10的补0
         * s - 秒
         */
        format: 'YYYY-DD-MM hh:mm:ss'
    }, option);

    var d;
    (!opt.date) ? d = new Date() : d = new Date(opt.date);
    if (!d) return false;

    var year = d.getFullYear(),
        month = d.getMonth(),
        date = d.getDate(),
        week = d.getDay(),
        hour = d.getHours(),
        minute = d.getMinutes(),
        seconds = d.getSeconds();
    var r = opt.format;
    var reg = /(Y{1,4}|M{1,4}|D{1,2}|W{1,2}|h{1,2}|m{1,2}|s{1,2})/g;
    return r.replace(reg, function(_r){
        switch (_r){
            case 'YYYY':
            case 'YYY':
            case 'YY':
            case 'Y':
                return year;
            case 'MMMM':
                return MONTH[month];
            case 'MMM':
                return MONTHSHORT[month];
            case 'MM':
                if ((month + 1) < 10) return '0' + (month + 1);
                return (month + 1);
            case 'M':
                return (month + 1);
            case 'DD':
                if (date < 10) return '0' + date;
                return date;
            case 'D':
                return date;
            case 'WW':
                return WEEK[week];
            case 'W':
                return WEEKSHORT[week];
            case 'hh':
                if (hour < 10) return '0' + hour;
                return hour;
            case 'h':
                return hour;
            case 'mm':
                if (minute < 10) return '0' + minute;
                return minute;
            case 'm':
                return minute;
            case 'ss':
                if (seconds < 10) return '0' + seconds;
                return seconds;
            case 's':
                return seconds;
        }
    });
}  


/**
 * dateConvertor()
 * 按指定格式转换日期字符串
 * @author: zhxming
 * 参数：
 * str：要转换的日期字符串
 * strFormat： str的格式
 * delimiter： str格式中的日期分隔符（默认日期分隔符為'/'，时间分隔符为':'）
 * returnFormat： 要返回的日期字符串格式
 * 日期字符串格式：
 * YYYY, YYY, YY, Y - 年。如2016
 * MM - 月。<10的补0，如05，12
 * M - 月。 不补0
 * MMMM - 月。 英文。如January
 * MMM - 月。英文简写。如Jan
 * DD - 日。<10的补0
 * D - 日。
 * WW - 星期。英文。如Sunday
 * W - 星期。英文简写。如Sun
 * hh - 小时。<10的补0
 * h - 小时。
 * mm - 分。<10的补0
 * m - 分。
 * ss - 秒。<10的补0
 * s - 秒
 */
var dateConvertor = function(str, strFormat, delimiter, returnFormat){
    var aDate = splitByFormat(str, delimiter, ':'),
        aFormat = splitByFormat(strFormat, delimiter, ':');
    var year = '', month = '', date = '', week = '', hour = '', minute = '', seconds = '';
    getFormatDate(aDate, aFormat);
    return setFormatDate(returnFormat);

    // 按格式分割字符串
    function splitByFormat(str, dateDelimiter, timeDelimiter){
        var _str = [];
        // 按空格拆分
        var s = str.split(' ');
        $.each(s, function(si, sv){
            // 按日期分隔符拆分
            var d = sv.split(dateDelimiter || '/');
            // 拆分成功
            if (d.length > 1){
                $.each(d, function(di, dv){
                    // 按时间分隔符拆分
                    var t = dv.split(timeDelimiter || ':');
                    if (t.length == 1){
                        // 拆分失败，结束拆分
                        _str.push(dv);
                    }else{
                        $.each(t, function(ti, tv){
                            _str.push(tv);
                        });
                    }
                });
            }
            // 拆分失败
            if (d.length == 1){
                // 按时间分隔符拆分
                var t = d.toString().split(':');
                if (t.length == 1){
                    // 拆分失败，结束拆分
                    _str.push(d.toString());
                }else{
                    $.each(t, function(ti, tv){
                        _str.push(tv);
                    });
                }
            }
        });
        return _str;
    }

    // 按格式获取各日期要素
    function getFormatDate(a, format){
        $.each(format, function(i, v){
            if (v.indexOf('Y') != -1) year = parseInt(a[i], 10);     
            if (v.indexOf('MMMM') != -1){
                for(var j = 0; j < MONTH.length; j++){
                    if (MONTH[j] == a[i]) month = j;
                }
            }else if (v.indexOf('MMM') != -1){
                for(var j = 0; j < MONTHSHORT.length; j++){
                    if (MONTHSHORT[j] == a[i]) month = j;
                }
            }else if (v.indexOf('M') != -1){
                month = parseInt(a[i], 10) - 1;
            }
            if (v.indexOf('D') != -1) date = parseInt(a[i], 10);
            if (v.indexOf('WW') != -1){
                for(var j = 0; j < WEEK.length; j++){
                    if (WEEK[j] == a[i]) week = j;
                }
            }else if (v.indexOf('W') != -1){
                for(var j = 0; j < WEEKSHORT.length; j++){
                    if (WEEKSHORT[j] == a[i]) week = j;
                }
            }
            if (v.indexOf('h') != -1) hour = parseInt(a[i], 10);
            if (v.indexOf('m') != -1) minute = parseInt(a[i], 10);
            if (v.indexOf('s') != -1) seconds = parseInt(a[i], 10);
        });
    }
    // 从格式生成日期字符串
    function setFormatDate(format){
        var reg = /(Y{1,4}|M{1,4}|D{1,2}|W{1,2}|h{1,2}|m{1,2}|s{1,2})/g;
        return format.replace(reg, function(_r){
            switch (_r){
                case 'YYYY':
                case 'YYY':
                case 'YY':
                case 'Y':
                    return year;
                case 'MMMM':
                    return MONTH[month];
                case 'MMM':
                    return MONTHSHORT[month];
                case 'MM':
                    if ((month + 1) < 10) return '0' + (month + 1);
                    return (month + 1);
                case 'M':
                    return (month + 1);
                case 'DD':
                    if (date < 10) return '0' + date;
                    return date;
                case 'D':
                    return date;
                case 'WW':
                    return WEEK[week];
                case 'W':
                    return WEEKSHORT[week];
                case 'hh':
                    if (hour < 10) return '0' + hour;
                    return hour;
                case 'h':
                    return hour;
                case 'mm':
                    if (minute < 10) return '0' + minute;
                    return minute;
                case 'm':
                    return minute;
                case 'ss':
                    if (seconds < 10) return '0' + seconds;
                    return seconds;
                case 's':
                    return seconds;
            }
        });
    }
}



/**
 * sanJumpto
 * ajax加载
 * @author: zhxming
 */
;(function($){
    'use strict';

    var config = {
        jumpType: 'ajax',
        //加载文件路径，默认从自定义属性data-url获取
        target: 'data-url',
        //指定加载文件路径，优先于target
        url: '',
        //加载对象不存在时默认指向url
        defaultUrl: 'temp.html',
        // GET || POST
        type: 'POST',
        cache: false,
        // 是否添加时间戳
        timestamp: true,
        async: true,
        data: null,
        //是否允许注入替换
        inject: true,
        //注入替换对象。属性名即页面中要替换的对象，必须以 {{ 和 }} 包裹住，当数据获取成功并且还未加载时，将被替换成对应的属性值
        injectedVar: {},
        //回调，加载开始前执行。
        onBefore: function(){},   
        //回调，成功获取数据后执行，该回调在注入替换之后，在onDone()之前执行
        onLoad: function(){},           
        //回调，成功获取数据，并且数据加载成功后执行。
        onDone: function(){},
        //回调，数据加载失败后执行。
        onFail: function(){},  
        //回调，不论加载成功或失败都的执行。在onDone()/onFail()之后执行
        onAlways: function(){}              
    }

    var methods = {
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this);
                opt.type = (opt.type + '').toUpperCase();
                $this.data('opt', opt);

                if (opt.jumpType == 'ajax') {
                    methods.ajax.call($this);
                }
            });
        },
        ajax: function(){
            return this.each(function(){
                var $this = $(this);
                var opt = $this.data('opt');

                var u = opt.url || $this.attr(opt.target) || opt.defaultUrl;
                if (opt.timestamp) {
                    u = san.tools.urlTimestamp(u);
                }

                $.ajax({
                    url: u,
                    cache: opt.cache,
                    async: opt.async,
                    type: opt.type,
                    data: opt.data,
                    beforeSend: function(){
                        opt.onBefore.call($this);
                    }
                }).done(function(data){
                    var html = data;
                    // 过滤标签，只保留<body></body>内内容
                    if (/(<body[^>]*>|<\/body[^>]*>)/gi.test(html)) {
                        html = html.replace(/^[\s\S]*<body[^>]*>/gi, '');
                        html = html.replace(/<\/body[^>]*>[\s\S]*/gi, '');
                    }

                    // 替换注入变量
                    // 属性名不能带有.
                    if (opt.inject){
                        html = html.replace(/\{\{([^(\}\})]*)\}\}/g, function(m, $1){
                            // var _m = m.replace(/(\{\{|\}\})/g, '');
                            var s;
                            if (~$1.indexOf('.')) {
                                var a = $1.split('.'),
                                    len = a.length,
                                    i = 0;
                                s = opt.injectedVar;
                                for (; i < len; i++) {
                                    s = s[a[i]];
                                    if (!s) {break;}
                                }
                            } else {
                                s = opt.injectedVar[$1]
                            }
                            // var s = opt.injectObj[$1];
                            return (s !== undefined) ? s : m;
                        });
                    }

                    // callback
                    opt.onLoad.call($this);

                    $.when($this.html(html).promise()).done(function(){
                        // callback
                        opt.onDone.call($this);
                    });
                }).always(function(){
                    opt.onAlways.call($this);
                }).fail(function(){
                    opt.onFail.call($this);
                });
            });
        }
    }

    $.fn.sanJumpto = function(){
        var jumpto = san.tools.objectCreate(san.widget);
        jumpto.init(this, methods, arguments);
    };
})(jQuery);   



/**
 * sanPagination，翻页
 * @author: zhxming
 */
;(function($){
    'use strict';

    var config = {
        // CLASS，分页容器
        pagination: 'san-pagination',
        // CLASS，翻页按钮，首页、前一页、后一页、尾页
        pageBtn: 'page-btn',
        pageFirst: 'page-first',
        pagePrev: 'page-prev',
        pageNext: 'page-next',
        pageLast: 'page-last',
        pageFirstText: '第一页',
        pagePrevText: '上一页',
        pageNextText: '下一页',
        pageLastText: '最后页',
        pageIcon: true,
        // 页码信息
        pageInfo: true,
        // CLASS，当前页码
        pageNum: 'page-number',
        // CLASS，总页码
        pageTotal: 'page-total',
        // 记录数信息
        recordsInfo: true,
        // CLASS，总记录数
        recordsTotal: 'records-total',
        // CLASS，节点禁用状态
        disabled: 'disabled',
        // 是否显示页码输入域
        inputJump: true,
        pageInput: 'page-input',
        //翻页是否返回顶部,默认false，为true时，backToTopId生效
        backToTop:false,
        //返回顶部位置的id
        backToTopId:'',
        // 设置对应容器内的值
        setup: {
            // 当前页码
            pageNum: 1,
            // 总页码
            pageTotal: 1,
            // 总记录数
            recordsTotal: 0
        },
        bindClick: true,
        /**
         * 点击翻页按钮后执行
         * $li - jQuery对象，当前按钮
         * prevNum - 翻页前（先前）的页码
         * curNum - 翻页后（当前）页码
         */
        onClick: function($li, prevNum, curNum){},
        /**
         * 按回车后执行
         * function($input, prevNum, curNum){}
         * $input - jQuery对象，输入域
         * prevNum - 翻页前（先前）的页码
         * curNum - 翻页后（当前）页码
         * 默认false，回车时执行onClick回调
         */
        onEnter: false
    }

    var namespace = 'sanPagination',
        handleMark = 'san-pagination';

    var methods = {
        init: function(option){
            return this.each(function(){
                var $this = $(this),
                    opt = $.extend(true, {}, config, option),
                    pagiId;

                pagiId = san.tools.uuid('san-pagination-');
                $this.attr(handleMark, pagiId);
                opt.pagiId = pagiId;
                $this.data('options', opt);

                // 创建DOM
                methods.build.call($this);

                // 点击翻页按钮
                $this.off(DEFAULT_EVENT + '.' + namespace, '.' + opt.pageBtn + '>a');
                $this.on(DEFAULT_EVENT + '.' + namespace, '.' + opt.pageBtn + '>a', function(e){
                    e.stopPropagation();
                    var $li = $(this).parent();
                    if ($li.hasClass(opt.disabled) || !opt.bindClick) {return false;}

                    var n = parseInt($this.find('.' + opt.pageNum).text(), 10),
                        t = parseInt($this.find('.' + opt.pageTotal).text(), 10),
                        c = 0;
                    
                    if ($li.hasClass(opt.pageFirst)){
                        c = 1;
                    }
                    if ($li.hasClass(opt.pageLast)){
                        c = t;
                    }
                    if ($li.hasClass(opt.pagePrev)){
                        c = n - 1;
                    }
                    if ($li.hasClass(opt.pageNext)){
                        c = n + 1;
                    }
                    
                    methods.toPage.call($this, c);
                    
                    // 回调
                    opt.onClick.call($this, $li, n, c);
                });

                // 页码输入域监听
                $this.off('keyup.' + namespace, '.' + opt.pageInput);
                $this.on('keyup.' + namespace, '.' + opt.pageInput, function(e){
                    var $input = $(this),
                        v = parseInt($input.val(), 10),
                        t = /^[1-9][0-9]*$/,
                        f = t.test(v);

                    var min = 1,
                        max = parseInt($this.find('.' + opt.pageTotal).text(), 10),
                        n = parseInt($this.find('.' + opt.pageNum).text(), 10);
                    if (!f || v > max) {v = '';}
		            $input.val(v);

                    if (e.keyCode == 13 && !!v){
                        methods.toPage.call($this, v);

                        if (san.tools.type(opt.onEnter) === 'function') {
                            opt.onEnter.call($this, $input, n, v);
                        } else {
                            opt.onClick.call($this, $input, n, v);
                        }

                        $(this).val('');
                    }
                });

                $this.attr('data-listener', 'media');
                san.listener.duplicated($this[0], MEDIA_LISTENER_GROUP);
                MEDIA_LISTENER_GROUP[pagiId] = $this[0];

                var waitingTimer;
                $this.on(MEDIA_LISTENER + '.' + namespace, function(e) {
                    clearInterval(waitingTimer);
                    waitingTimer = setInterval(function(){
                        if (GLOBE_INIT) {
                            clearInterval(waitingTimer);
                            var $turning = $this.find('.' + opt.pageFirst),
                                $br = $this.find('br');
                            if ($br.length) {
                                $br.remove();
                            }
                            if (V_VW >= MEDIA_RULE.S) {return false;}
                            $turning.before('<br>');
                        }
                    }, 10);
                }).trigger(MEDIA_LISTENER + '.' + namespace);

            });
        },
        /**
         * 创建节点HTML结构
         * data - 生成节点的数据，json字符串
         * level - 节点级别
         */
        build: function(data, level){
            var $this = this,
                opt = $this.data('options');
            // 翻页按钮
            var strPageBtn = opt.pageBtn,
                strPageIcon = opt.pageIcon ? 'class="page-icon" ' : '';
            var strPage = '<li class="' + strPageBtn + ' ' + opt.pageFirst + '"><a ' + strPageIcon + 'href="javascript:void(0);" title="' + opt.pageFirstText + '">' + opt.pageFirstText + '</a></li>';
            strPage += '<li class="' + strPageBtn + ' ' + opt.pagePrev + '"><a ' + strPageIcon + 'href="javascript:void(0);" title="' + opt.pagePrevText + '">' + opt.pagePrevText + '</a></li>';
            strPage += '<li class="' + strPageBtn + ' ' + opt.pageNext + '"><a ' + strPageIcon + 'href="javascript:void(0);" title="' + opt.pageNextText + '">' + opt.pageNextText + '</a></li>';
            strPage += '<li class="' + strPageBtn + ' ' + opt.pageLast + '"><a ' + strPageIcon + 'href="javascript:void(0);" title="' + opt.pageLastText + '">' + opt.pageLastText + '</a></li>';
            // 页码信息
            var strInfo = '<li class="page-size"><span><i class="' + opt.pageNum + '"></i>/<i class="' + opt.pageTotal + '"></i> 页</span></li>';
            // 记录信息
            var strRec = '<li class="records-size"><span>共 <i class="' + opt.recordsTotal + '"></i> 条记录</span></li>';
            // 页面输入域
            var strInput = '<li class="page-input"><span>跳到第 <input class="' + opt.pageInput + '" type="text" value="" /> 页</span></li>';

            $this.html(strPage);
            if (opt.pageInfo) {$this.prepend(strInfo);}
            if (opt.recordsInfo) {$this.prepend(strRec);}
            if (opt.inputJump) {$this.append(strInput);}
            // 设置值和状态
            methods.setup.call($this, opt.setup);
        },
        /**
         * 设置各项目的值及对应的状态
         * 包括当前页码、总页码、总记录数
         */
        setup: function(option){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $pageNum = $this.find('.' + opt.pageNum),
                    $pageTotal = $this.find('.' + opt.pageTotal),
                    $recTotal = $this.find('.' + opt.recordsTotal),
                    $pageInput = $this.find('.' + opt.pageInput);
                
                opt.setup = $.extend({}, opt.setup, option);
                var pn = opt.setup.pageNum,
                    pt = opt.setup.pageTotal,
                    rt = opt.setup.recordsTotal;
                $pageNum.text(pn);
                $pageTotal.text(pt);
                $recTotal.text(rt);
                $pageInput.val(''); //.prop('disabled', false);

                if (pn == 1){
                    methods.disabled.call($this, $this.find('.' + opt.pageFirst));
                    methods.disabled.call($this, $this.find('.' + opt.pagePrev));
                }else{
                    methods.enabled.call($this, $this.find('.' + opt.pageFirst));
                    methods.enabled.call($this, $this.find('.' + opt.pagePrev));
                }
                if (pn >= pt){
                    methods.disabled.call($this, $this.find('.' + opt.pageNext));
                    methods.disabled.call($this, $this.find('.' + opt.pageLast));
                }else{
                    methods.enabled.call($this, $this.find('.' + opt.pageNext));
                    methods.enabled.call($this, $this.find('.' + opt.pageLast));
                }
            });
        },
        /**
         * 设置为禁用状态
         * $li - jQuery对象，要禁用的节点
         */
        disabled: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                
                $li.addClass(opt.disabled);
            });
        },
        /**
         * 取消禁用状态
         * $li - jQuery对象，要禁用的节点
         */
        enabled: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                
                $li.removeClass(opt.disabled);
            });
        },
        /**
         * 到指定页码
         * n - 指定页码
         */
        toPage: function(n){

            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $pageNum = $this.find('.' + opt.pageNum),
                    $pageTotal = $this.find('.' + opt.pageTotal),
                    $pageFirst = $this.find('.' + opt.pageFirst),
                    $pageLast = $this.find('.' + opt.pageLast),
                    $pageNext = $this.find('.' + opt.pageNext),
                    $pagePrev = $this.find('.' + opt.pagePrev);
								var tt = 0;
								var ofst1 = 0;
								if(opt.backToTop){
									if(opt.backToTopId!=''){
										tt = $("#"+opt.backToTopId).offset().top;
										if(MEDIA_CASE=='XS' || MEDIA_CASE =="S"){
				            	ofst1 =112;
				            }
									}
								}
								$("html,body").animate({scrollTop: tt-ofst1}, 100);
								
                var c = parseInt($pageNum.text(), 10),
                    t = parseInt($pageTotal.text(), 10);
                if (n < 1) {n = 1};
                if (n > t) {n = t};
                if (n == 1){
                    $this.find('.' + opt.pageNum).text(1);
                    methods.disabled.call($this, $pageFirst);
                    methods.disabled.call($this, $pagePrev);
                    methods.enabled.call($this, $pageNext);
                    methods.enabled.call($this, $pageLast);
                    return 1;
                }
                if (n == t){
                    $this.find('.' + opt.pageNum).text(t);
                    methods.enabled.call($this, $pageFirst);
                    methods.enabled.call($this, $pagePrev);
                    methods.disabled.call($this, $pageNext);
                    methods.disabled.call($this, $pageLast);
                    return t;
                }
                $pageNum.text(n);
                if ($pagePrev.hasClass(opt.disabled)){
                    methods.enabled.call($this, $pageFirst);
                    methods.enabled.call($this, $pagePrev);
                }
                if ($pageNext.hasClass(opt.disabled)){
                    methods.enabled.call($this, $pageNext);
                    methods.enabled.call($this, $pageLast);
                }
                return n;
            });
        }
    }

    $.fn.sanPagination = function(){
        var pagi = san.tools.objectCreate(san.widget);
        return pagi.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanMaskLayer 遮罩层
 * @author: zhxming
 */
;(function($){
    'use strict';

    var config = {
        active: 'san-mask-active',
        type: 'loading',
        imgUrl: '',
        text: '正在加载，请稍候……'
    }

    var methods = {
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this);
                $this.data('maskOption', opt);
                $this.attr('data-mask', 'san-mask-' + (new Date()).valueOf());
                
                var mask = '<div class="san-mask" data-mask="san-mask' + (new Date()).valueOf() + '">';
                if (opt.type == 'loading'){
                    mask += '<div class="san-mask-loading">';
                    if (opt.imgUrl){
                        mask += '<img src="' + opt.imgUrl + '"/>';
                    }
                    if (opt.text){
                        mask += '<p>' + opt.text + '</p>';
                    }
                    mask += '</div><span class="v"></span>'
                }
                mask += '</div>';
                $this.addClass(opt.active).append(mask);
            });
        },
        remove: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('maskOption'),
                    $mask = $this.find('.san-mask');
                if (san.tools.isEmptyObject(opt)) {return;}
                if ($mask.length){
                    $this.removeClass(opt.active).find('.san-mask').remove();
                }
            });
        }
    }

    $.fn.sanMaskLayer = function(){
        var mask = san.tools.objectCreate(san.widget);
        return mask.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanSlide
 * 幻灯片/跑马灯
 * @author: zhxming
 */
;(function($){
    'use strict';

    var config = {
        // CLASS，跑马灯/幻灯片容器
        slide: 'san-slide',
        // 显示框
        frame: 'san-slide-frame',
        // 显示内容列表容器（li列表）
        list: 'san-slide-list',
        // CLASS，当前激活项
        active: 'active',
        /**
         * 运行类型。scroll || slide
         * scroll：（默认）卷轴模式。一次显示多个项目
         * slide：幻灯片模式。一次仅显示一个项目
         */
        type: 'scroll',
        // 是否启用方向箭头导航
        dirNav: true,
        // CLASS，方向箭头样式
        dirClass: 'san-slide-dir-nav',
        dirPrev: 'san-slide-dir-prev',
        dirNext: 'san-slide-dir-next',
        dirDisabled: 'disabled',
        // 是否启用目录导航
        ctrlNav: false,
        // CLASS，目录导航样式
        ctrlClass: 'san-slide-ctrl-nav',
        // 默认显示项
        defaultUnit: 0,
        // 单次滑动项（li）数量
        moveUnits: 1,
        /**
         * 滑动模式
         * true||false。循环模式||非循环模式
         */
        loop: false,
        /**
         * 滑动方向
         * h||H-水平方向（默认），v||V-垂直方向
         */
        dir: 'h',
        // 显示框的宽度。默认null，显示框由CSS决定
        frameWidth: null,
        /**
         * 显示框高度
         * null（默认）|| number(px)
         * null时，由css定义
         * number仅在dir: v||V时有效
         */
        frameHeight: null,
        // 滑动速度（毫秒）
        speed: 300,
        // 自动滑动
        // true时，所有回调均不执行
        autoMove: true,
        // 自动滑动间隔（毫秒）
        interval: 5000,
        // 鼠标移入后停止自动滑动
        hoverPaused: true,
        touchMove: false,
        /**
         * 滑动后执行
         * this - jquery对象，滑动器
         * $cur - jquery对象，滑动完成后的当前项。（当前项指滑动器列表在可视区域内显示的第一个元素）
         * $pre - jquery对象，滑动执行前的当前项
         */
        onMove: function($cur, $pre){},
        /**
         * 滑动到起点后执行。
         * loop: false时有效，此回调方法在onMove后执行
         * this - jquery对象，滑动器
         * $li - jquery对象，滑动器列表在可视区域内显示的第一个元素
         */
        onFirst: function($li){},
        /**
         * 滑动到终点后执行。
         * 注意：
         * 1.$li并不一定是最后一个元素
         * 2.在type: scroll时，用目录导航按钮触发移动时，可以多次触发此事件
         * loop: false时有效，此回调方法在onMove后执行
         * this - jquery对象，滑动器
         * $li - jquery对象，滑动器列表在可视区域内显示的第一个元素
         */
        onLast: function($li){}
    }

    var namespace = 'sanSlide',
        scrollTimmer = null;

    var methods = {
        init: function(option){
            return this.each(function(){
                clearInterval(scrollTimmer);
                var opt = $.extend({}, config, option);
                var $this = $(this),
                    $list = $this.find('.' + opt.list),
                    $frame = null,
                    $prev = null,
                    $next = null,
                    $ctrlNav = null,
                    slideId;

                slideId = san.tools.uuid('san-slide-');
                $this.attr('data-slide', slideId);
                opt.slideId = slideId;
                
                opt.dir = opt.dir.toLowerCase();
                if (opt.dir !== 'v') {opt.dir = 'h';}
                opt.type = opt.type.toLowerCase();
                if (opt.type === 'slide') {opt.moveUnits = 1;}

                $this.data('options', opt);

                var frame = opt.frame,
                    moveUnits = parseInt(opt.moveUnits, 10),
                    active = opt.active,
                    dirClass = opt.dirClass,
                    dirPrev = opt.dirPrev,
                    dirNext = opt.dirNext,
                    dirDisabled = opt.dirDisabled,
                    ctrlClass = opt.ctrlClass;

                $this.attr({
                    'data-listener': 'media',
                    'data-type': opt.type
                });
                san.listener.duplicated($this[0], MEDIA_LISTENER_GROUP);
                MEDIA_LISTENER_GROUP[slideId] = $this[0];
                
                if (!$list.parent('.' + frame).length){
                    $list.wrap('<div class="' + frame + '"></div>');
                }
                $frame = $this.find('.' + frame);
                
                // 设置
                setup.call($this);
                
                // 方向按钮
                $this.off(DEFAULT_EVENT + '.' + namespace, '.' + dirClass);
                $this.on(DEFAULT_EVENT + '.' + namespace, '.' + dirClass + ':not(.' + dirDisabled + ')', function(){
                    var $nav = $(this),
                        index = parseInt($list.children('.' + active + '[data-index]').attr('data-index'), 10),
                        edge = parseInt($list.children('.frame-edge[data-index]').attr('data-index'), 10);
                    index = Math.min(index, edge);
                    if ($nav.hasClass(dirNext)) {
                        index = index + moveUnits;
                        $this.find('.' + opt.dirPrev).removeClass(dirDisabled);
                    } else {
                        index = index - moveUnits;
                        $this.find('.' + opt.dirNext).removeClass(dirDisabled);
                    }
                    methods.goto.call($this, index);
                });

                // 目录按钮
                $this.off(DEFAULT_EVENT + '.' + namespace, '.' + ctrlClass);
                $this.on(DEFAULT_EVENT + '.' + namespace, '.' + ctrlClass + '>a:not(.' + active + ')', function(){
                    var $ctrl = $(this),
                        index = parseInt($ctrl.attr('data-index'), 10);
                    methods.goto.call($this, index);
                });

                if (opt.autoMove) {methods.autoMoving.call($this);}

                $this.on(MEDIA_LISTENER + '.' + namespace, function(e){
                    methods.reset.call($(this));
                });

                // 触摸事件
                if (!HASTOUCH || !opt.touchMove) {return;}

                $this[0].addEventListener('touchstart', function(e){
                    var self = this;
                    var touch = event.targetTouches[0],
                        startPos = {
                            x: touch.pageX,
                            y: touch.pageY,
                            time: +new Date()
                        },
                        endPos = null,
                        // 滚屏方向。0-横向，1-纵向
                        dir = 0,
                        // 手指滑动方向。-1-右滑，1-左滑
                        move = 1,
                        // 手指滑动持续时间
                        duration = 0,
                        $cur = $list.children('.' + active),
                        index = parseInt($cur.attr('data-index'), 10);
                    
                    e.stopPropagation();
                    
                    if(e.targetTouches.length > 1) {return};
                    
                    self.addEventListener('touchmove', moving, false);    
                    self.addEventListener('touchend', moved, false);
                    
                    function moving(e) {
                        e.stopPropagation();

                        if(e.targetTouches.length > 1) {return};

                        var touch = e.targetTouches[0];
                        endPos = {
                            x:touch.pageX - startPos.x,
                            y:touch.pageY - startPos.y
                        };
                        move = endPos.x >= 0 ? -1 : 1;
                        dir = Math.abs(endPos.x) < Math.abs(endPos.y) ? 1 : 0;
                        if (dir === 0) {
                            e.preventDefault();
                        }
                    }
                    
                    function moved(e) {
                        e.stopPropagation();
                        duration = parseFloat(+new Date() - startPos.time);
                        if (dir === 0 && duration > 200) {
                            if (~move) {
                                index++;
                            } else {
                                index--;
                            }
                            methods.goto.call($this, index);
                        }
                        self.removeEventListener('touchmove', moving, false);
                        self.removeEventListener('touchend', moved, false);
                    }
                });
            });
        },
        /**
         * 显示指定项
         * index - 指定项索引号
         * animate - 是否执行动画
         * runCallback - 是否执行回调
         */
        goto: function(index, animate, runCallback) {
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $frame = $this.find('.' + opt.frame),
                    $list = $this.find('.' + opt.list),
                    $li = null,
                    $dirPrev = null,
                    $dirNext = null,
                    $ctrlNav = null,
                    $pre = $list.children('.active[data-index]'),
                    $cur = null;
                
                animate = animate === false ? false : true;
                runCallback = (runCallback === false || opt.autoMove) ? false : true;
                
                var dirNav = opt.dirNav,
                    dirDisabled = opt.dirDisabled,
                    ctrlNav = opt.ctrlNav,
                    type = opt.type,
                    active = opt.active,
                    loop = opt.loop,
                    dir = (opt.dir === 'v') ? 'top' : 'left',
                    len = parseInt($list.attr('data-total'), 10),
                    listSize = (dir === 'top') ? $list.outerHeight(true) : $list.outerWidth(true),
                    frameSize = (dir === 'top') ? $frame.height() : $frame.width(),
                    offset = 0,
                    _offset = 0,
                    atLast = false;

                index = index >= 0 ? Math.min(index, len - 1) : 0;
                $cur = $list.children('[data-index="' + index + '"]');
                
                $list.removeClass('last');

                if (dirNav) {
                    $dirPrev = $this.find('.' + opt.dirPrev);
                    $dirNext = $this.find('.' + opt.dirNext);
                    $dirPrev.removeClass(dirDisabled);
                    $dirNext.removeClass(dirDisabled);
                }
                
                if (ctrlNav) {
                    $ctrlNav = $this.find('.' + opt.ctrlClass);
                    $ctrlNav.find('[data-index="' + index + '"]').addClass(active).siblings().removeClass(active);
                }
                
                var i = index, _i = index, j = 0;
                for (i = index; i >= j; i--) {
                    _offset = (dir === 'top') ? $list.children('[data-index="' + i + '"]')[0].offsetTop : $list.children('[data-index="' + i + '"]')[0].offsetLeft;
                    if (listSize - _offset >= frameSize) {
                        index = _i;
                        if (index === 0) {
                            if (dirNav) {
                                $dirPrev.addClass(dirDisabled);
                            }
                        } else if (index === (len - 1)) {
                            if (dirNav) {
                                $dirNext.addClass(dirDisabled);
                            }
                            $list.addClass('last');
                            atLast = true;
                        }
                        break;
                    }
                    $list.addClass('last');
                    atLast = true;
                    _i = i;
                    if (dirNav) {
                        $dirNext.addClass(dirDisabled);
                    }
                }
                $li = $list.children('[data-index="' + index + '"]');
                offset = (dir === 'top') ? $li[0].offsetTop : $li[0].offsetLeft;
                _offset = offset === 0 ? 0 : '-' + offset + 'px';

                // $li.addClass(active).siblings().removeClass(active);
                $li.addClass('frame-edge').siblings().removeClass('frame-edge');
                $cur.addClass(active).siblings().removeClass(active);

                if (animate) {
                    if (dir === 'left'){
                        $list.animate({'left': _offset}, opt.speed, runback);
                    } else if (dir === 'top') {
                        $list.animate({'top': _offset}, opt.speed, runback);
                    }
                } else {
                    $list.css(dir, _offset);
                    runback();
                }

                function runback() {
                    if (!runCallback) {return;}
                    opt.onMove.call($this, $cur, $pre);
                    var current = parseInt($list.children('.' + active).attr('data-index'), 10),
                        edge = parseInt($list.children('.frame-edge').attr('data-index'), 10);
                    if (edge === 0) {
                        opt.onFirst.call($this, $cur, $pre);
                    }
                    if (atLast && current >= edge) {
                        opt.onLast.call($this, $cur, $pre);
                    }
                }
            });
        },
        /**
         * 自动滑动
         */
        autoMoving: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $list = $this.find('.' + opt.list),
                    $dirPrev = $this.find('.' + opt.dirPrev),
                    $dirNext = $this.find('.' + opt.dirNext),
                    $cur = null,
                    index = 0,
                    moveUnits = parseInt(opt.moveUnits, 10),
                    interval = opt.interval,
                    slide;

                if (V_VW < MEDIA_RULE.M) { return; }
                
                function moving(){
                    slide = $this.data('data-slide');
                    $cur = $list.children('.' + opt.active);
                    index = parseInt($cur.attr('data-index'), 10);
                    if (!document.getElementById($this[0].id)) {
                        $this.off('mouseenter mouseleave');
                        clearInterval(scrollTimmer);
                    }
                    if (!slide) {return false;}

                    if (!$list.hasClass('last')){
                        methods.goto.call($this, index + moveUnits);
                    }else{
                        methods.reset.call($this, true);
                    }
                }

                scrollTimmer = setInterval(moving, interval);

                if (opt.hoverPaused){
                    $this.off('mouseenter.' + namespace +' mouseleave.' + namespace);
                    $this.on('mouseenter.' + namespace, function(){
                        clearInterval(scrollTimmer);
                    }).on('mouseleave.' + namespace, function(){
                        scrollTimmer = setInterval(moving, interval);
                    });
                }
            });
        },
        /**
         * 重置滑动器
         * animate - 是否执行动画效果，默认true。
         * 注意：loop:true时不管animate是何值均无动画效果。
         * callback - 回调方法。重置完成后执行。
         */
        reset: function(animate, runCallback, callback){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');

                animate = (animate === false) ? false : true;
                runCallback = (runCallback === true) ? true : false;
                
                if (opt.autoMove) {
                    $this.off('mouseenter mouseleave');
                    clearInterval(scrollTimmer);
                }
                
                setup.call($this, animate, runCallback);

                if (callback && typeof animate === 'function') {
                    callback.call($this);
                }

                if (opt.autoMove) {
                    methods.autoMoving.call($this);
                }
            });
        }
    }

    var setup = function(animate, runCallback){
        var $this = $(this),
            opt = $this.data('options'),
            $list = $this.find('.' + opt.list),
            $frame = $this.find('.' + opt.frame),
            $dirPrev = null,
            $dirNext = null,
            $ctrlNav = null;
        
        animate = (animate === false) ? false : true;
        runCallback = (runCallback === true) ? true : false;

        var type = opt.type,
            dir = (opt.dir == 'v') ? 'top' : 'left',
            dirNav = opt.dirNav,
            dirClass = opt.dirClass,
            dirDisabled = opt.dirDisabled,
            ctrlNav = opt.ctrlNav,
            ctrlClass = opt.ctrlClass,
            hasDirNav = $this.find('.' + dirClass).length ? true : false,
            hasCtrlNav = $this.find('.' + ctrlClass).length ? true : false,
            defaultUnit = parseInt(opt.defaultUnit, 10) || 0,
            frameWidth = parseFloat(opt.frameWidth) || $frame.innerWidth(),
            frameHeight = parseFloat(opt.frameHeight),
            listWidth = 0,
            listHeight = 0,
            len = 0,
            slide = true;
        
        if (dirNav && !hasDirNav) {
            var dirStr = '';
            dirStr += '<a class="' + dirClass + ' ' + opt.dirPrev + '" href="javascript:void(0);"></a>';
            dirStr += '<a class="' + dirClass + ' ' + opt.dirNext + '" href="javascript:void(0);"></a>';
            $this.append(dirStr);
            hasDirNav = true;
        }
        $dirPrev = $this.find('.' + opt.dirPrev);
        $dirNext = $this.find('.' + opt.dirNext);

        var ulw = 0, strCtrl = '';
        $list.children().each(function(i){
            var $li = $(this);
            $li.attr('data-index', i);
            if (type === 'slide') {
                $li.css('width', frameWidth + 'px');
            }
            if (dir === 'top') {
                listHeight += $li.outerHeight(true);
            } else {
                listWidth += $li.outerWidth(true);
            }
            if (ctrlNav && !hasCtrlNav) {
                strCtrl += '<a data-index="' + i + '" href="javascript:void(0);">' + (i + 1) + '</a>';
            }
            len = i + 1;
        });

        $list.attr('data-total', len);

        if (ctrlNav && !hasCtrlNav) {
            $this.append('<div class="' + ctrlClass + '">' + strCtrl + '</div>');
            hasCtrlNav = true;
        }
        $ctrlNav = $this.find('.' + ctrlClass);

        if (dir === 'left'){ 
            $list.css('width', listWidth + 'px');
            if (listWidth <= frameWidth) {
                slide = false;
            }
        } 
        if (dir === 'top') {
            if (frameHeight) {
                $frame.css('height', frameHeight + 'px');
            } else {
                frameHeight = $frame.height();
            }
            listHeight = $list.outerHeight(true);
            if (listHeight <= frameHeight){
                slide = false;
            }
        }

        // 是否可滑动。当项数不足时设为false不滑动
        $this.data('data-slide', slide);

        if (!slide) {
            if (dirNav) {
                $dirPrev.addClass(dirDisabled);
                $dirNext.addClass(dirDisabled);
            }
            if (ctrlNav) {
                $ctrlNav.addClass('NONE');
            }
            return;
        }
        if (defaultUnit <= 0) {
            defaultUnit = 0;
        } else {
            defaultUnit = Math.min(d, (len - 1));
        }

        methods.goto.call($this, defaultUnit, animate, runCallback);
    }

    $.fn.sanSlide = function(){
        var sanSlide = san.tools.objectCreate(san.widget);
        return sanSlide.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanTree，目录树结构
 * @author: zhxming
 * 节点数据来自json（外部文件或本地字符串）
 */
;(function($){
    'use strict';

    var config = {
        // CLASS，目录树容器
        tree: 'san-tree',
        // CLASS，节点
        nodes: 'san-tree-node',
        // CLASS，节点名
        nodesName: 'node-name',
        // CLASS，节点名文本
        nodesText: 'node-text',
        // CLASS，节点徽标
        nodesBadge: 'node-badge',
        // CLASS，当前节点
        current: 'current',
        // CLASS，节点禁用状态
        disabled: 'disabled',
        // CLASS，节点隐藏状态
        hide: 'hide',
        // CLASS，节点折叠状态
        fold: 'fold',
        // CLASS，节点展开状态
        unfold: 'unfold',
        // 折叠所有节点（根节点除外）
        foldAll: false,
        // 展开所有节点
        unfoldAll: false,
        // 节点缩进。单位像素
        nodesIndent: 10,
        //数据来源。值：'remote'（默认，远程） || 'local'（本地）
        dataSource: 'remote',
        // 远程json文件链接或本地json字符串
        url: '',
        // json中的数据源属性名（即节点属性的父级）
        dataField: 'data',
        // json中的节点属性名
        nodesField: 'nodes',
        // 是否显示徽标
        badge: false,
        // json数据加载前执行
        onBeforeLoad: function(){},
        // json数据加载成功后执行
        onDone: function(){},
        // json数据加载失败后执行
        onFail: function(){},
        // 点击节点开关后执行。$obj - 当前节点
        onSwitch: function($obj){},
        // 点击节点名后执行。$obj - 当前节点
        onClick: function($obj){}
    }

    var methods = {
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this);
                $this.data('options', opt)

                // 加载数据
                methods.load.call($this);

                // 点击节点名称执行
                $this.off('click.sanTree', '.' + opt.nodesName);
                $this.on('click.sanTree', '.' + opt.nodesName, function(e){
                    e.stopPropagation();
                    var $li = $(this).closest('.' + opt.nodes);
                    if ($li.hasClass(opt.disabled)) { return false; }
                    // 选中节点
                    methods.nodesCheck.call($this, $li);
                    // 回调
                    opt.onClick.call($this, $li);
                });

                // 点击节点开关执行
                $this.off('click.sanTree', '.' + opt.nodes);
                $this.on('click.sanTree', '.' + opt.nodes, function(e){
                    e.stopPropagation();
                    var $li = $(this);
                    if ($li.hasClass(opt.disabled) || $li.find('.' + opt.nodes).length == 0) { return false; }
                    //展开/折叠节点
                    if ($li.hasClass(opt.fold)){
                        methods.unfold.call($this, $li);
                    }else{
                        methods.fold.call($this, $li);
                    }
                    // 回调
                    opt.onSwitch.call($this, $li);
                });
            });
        },
        /**
         * 加载数据
         * url - 同config。不设置即取config中的值
         * dataSource - 同config。不设置即取config中的值
         * runCallback - 是否执行回调。Boolean，默认：true。
         */
        load: function(url, dataSource, runCallback){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                
                var _url = url || opt.url,
                    _dataSource = dataSource || opt.dataSource,
                    _runCallback = (runCallback === false) ? false : true;
                // 远程
                if (_dataSource == 'remote'){
                    $.ajax({
                        url: san.tools.urlTimestamp(_url),
                        type: 'POST',
                        dataType: 'json',
                        cache: false,
                        beforeSend: function(){
                            //回调
                            if (_runCallback) {opt.onBeforeLoad.call($this)};
                        }
                    }).done(function(data){
                        // json数据格式，暂定数据源来自'data'
                        var _data = (typeof data == 'string') ? $.parseJSON(data[opt.dataField]) : data[opt.dataField];
                        // 解析生成HTML结构
                        var html = methods.build.call($this, _data, 0);
                        $this.html(html);
                        //回调
                        if (_runCallback) {opt.onDone.call($this);}
                        return;
                    }).fail(function(){
                        if (_runCallback) {opt.onFail.call($this)};
                        return;
                    });
                }
                // 本地
                if (_dataSource == 'local'){
                    //获取数据
                    var _data = (typeof _url == 'string') ? $.parseJSON(_url) : _url;

                    //回调
                    if (_runCallback) {opt.onBeforeLoad.call($this);}

                    var $state = $.Deferred();
                    $.when(localBuild($this, _data, $state)).done(function(){
                        //回调
                        if (_runCallback) {opt.onDone.call($this);}
                    }).fail(function(){
                        //回调
                        if (_runCallback) {opt.onFail.call($this);}
                    });
                    return;
                }

                function localBuild($obj, data, $state){
                    var html = methods.build.call($obj, data, 0);
                    $obj.html(html);
                    return $state.promise();
                }
            });
        },
        /**
         * 创建节点HTML结构
         * data - 生成节点的数据，json字符串
         * level - 节点级别
         */
        build: function(data, level){
            var $this = this,
                opt = $this.data('options');
            level = parseInt(level, 10);
            var li = '',
                html = buildNodes(data, level);
            return html;
            
            // 生成HTML结构并返回
            function buildNodes(data, level){
                var _level = level + 1;
                $.each(data[opt.nodesField], function(n, v){
                    // json中预设的节点状态
                    var fold = null, disabled = null, hide = null;
                    fold = (v['fold'] || v['fold'] == 'true' || v['disabled'] || v['disabled'] == 'true') ? ' ' + opt.fold : ' ' + opt.unfold;
                    disabled = (v['disabled'] || v['disabled'] == 'true') ? ' ' + opt.disabled : '';
                    hide = (v['hide'] || v['hide'] == 'true') ? ' ' + opt.hide : '';

                    if (opt.foldAll) {fold = ' ' + opt.fold;}
                    if (opt.unfoldAll) {fold = ' ' + opt.unfold;}
                    if (!v[opt.nodesField]) {fold = ' ' + opt.fold;}

                    // 对应json结构：data-nid: 当前节点id，data-pid：父节点id
                    li += '<li class="' + opt.nodes + fold + disabled + hide + '" data-nid="' + v['id'] + '" data-level="' + level + '">';
                    li += '<div data-for="node">';
                    li += '<span class="node-switch" style="margin-left: ' + (_level * parseInt(opt.nodesIndent, 10)) + 'px;"></span>';
                    li += '<a class="' + opt.nodesName + '" href="javascript:void(0);">';
                    li += '<span class="' + opt.nodesText + '">' + v['name'] + '</span>';
                    if (opt.badge){
                        li += '<span class="' + opt.nodesBadge + '">' + v['badge'] + '</span>';
                    }
                    li += '</a></div>';
                    if (v[opt.nodesField]){
                        li += '<ul>';
                        li = buildNodes(v, _level) + '</ul>';
                    }
                    li += '</li>';
                });
                return li;
            }
        },
        /**
         * 折叠节点
         * $li - jQuery对象，要折叠的节点
         */
        fold: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                $li.addClass(opt.fold).removeClass(opt.unfold);
            });
        },
        /**
         * 展开节点
         * $li - jQuery对象，要折叠的节点
         */
        unfold: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                $li.addClass(opt.unfold).removeClass(opt.fold);
            });
        },
        /**
         * 折叠全部节点
         */
        foldAll: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                $this.find('.' + opt.nodes).each(function(){
                    if ($(this).find('.' + opt.nodes).length == 0) { return; }
                    methods.fold.call($this, $(this));
                });
            });
        },
        /**
         * 展开全部节点
         */
        unfoldAll: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                $this.find('.' + opt.nodes).each(function(){
                    if ($(this).find('.' + opt.nodes).length == 0) { return; }
                    methods.unfold.call($this, $(this));
                });
            });
        },
        /**
         * 设置节点为禁用状态
         * $li - jQuery对象，要禁用的节点
         */
        disabled: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                $li.addClass(opt.disabled).find('.' + opt.nodes).removeClass(opt.disabled);
            });
        },
        /**
         * 设置节点为隐藏状态
         * $li - jQuery对象，要隐藏的节点
         */
        hide: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                $li.addClass(opt.hide).find('.' + opt.nodes).removeClass(opt.hide);
            });
        },
        /**
         * 插入节点
         * data - 用于生成节点的数据，json字符串
         * $li - jQuery对象，在该节点后插入节点
         */
        nodesAppend: function(data, $li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                var level = parseInt($li.attr('data-level'), 10);

                var $ul = $li.children('ul');
                if ($ul.length == 0) {
                    $li.append('<ul></ul>');
                    $ul = $li.children('ul');
                }
                // 插入并展开当前节点
                $ul.append(methods.build.call($this, data, level + 1));
                methods.unfold.call($this, $li);
            });
        },
        /**
         * 选中节点
         * $li - jQuery对象，要选中的节点
         */
        nodesCheck: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                
                $this.find('.' + opt.nodes).removeClass(opt.current);
                $li.addClass(opt.current);
            });
        },
        /**
         * 删除节点
         * $li - jQuery对象，要删除的节点
         */
        nodesDelete: function($li){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options');
                var $parent = $li.parent().closest('.' + opt.nodes);
                $li.remove();
                // 折叠无子节点的节点
                if ($parent.find('.' + opt.nodes).length == 0){
                    methods.fold.call($this, $parent);
                }
            });
        }
    }

    $.fn.sanTree = function(){
        var tree = san.tools.objectCreate(san.widget);
        return tree.init(this, methods, arguments);
    };
})(jQuery);



/**
 * sanTemplate
 * 模板字符串
 * @author: zhxming
 **/
;(function($, window, undefined) {
    'use strict';

    var config = {
        // 数据源
        data: null,
        // null || id。如是内嵌的template，设为null，否则需通过id获取
        template: null,
        // 字符串生成后是否删除模板字符串。如要保留模板字符串重复使用，不要使用内嵌template
        deleteTemplate: true,
        // 获取到模板字符串之后，解析之前（包括移除模板元素之前）执行。str：获取到的字符串。可将str返回。
        onBefore: function(str){},
        // 模板字符串解析完成之后执行。str：解析完成后的字符串。可将str返回。
        onReady: function(str){},
        // 将解析完成后的字符串插入到DOM后执行。
        onDone: function(){}
    }

    var regHasCmd =  /<(\w+)[^>]+((\*san\-(?:if|for))="([^"]+)")[^>]*>/im,
        regCmdTags = /<(\w+)[^>]+((\*san\-(?:if|for))="([^"]+)")[^>]*>[\d\D]*<\/\1>/im,
        regSelfClosingTag = /(area|br|col|embed|hr|img|input|link|meta|param)/i; 

    regHasCmd = /<(\w+)(?:"[^"]*"|'[^']*'|[^'">])+((\*san\-(?:if|for))=(?:"([^"]+)"|'([^']+)'))(?:"[^"]*"|'[^']*'|[^'">])*>/im;
    regCmdTags = /<(\w+)(?:"[^"]*"|'[^']*'|[^'">])+((\*san\-(?:if|for))=(?:"([^"]+)"|'([^']+)'))(?:"[^"]*"|'[^']*'|[^'">])*>[\d\D]*<\/\1>/im;

    var methods = {
        init: function(option) {
            return this.each(function() {
                var $this = $(this);
                var opt = $.extend({}, config, option);
                var tpl = document.getElementById(opt.template), 
                    tagName,
                    text = '', 
                    html = '';
                var back = null;
                if (!tpl) {
                    tpl = $this.find('template')[0];
                }
                tagName = tpl.tagName.toLowerCase();
                if (tagName === 'template') {
                    text = fixed(tpl.innerHTML);
                } else if (tagName === 'script') {
                    text = fixed(tpl.text);
                }
                back = opt.onBefore.call($this, text);
                if (back) {
                    text = back;
                    back = null;
                }
                if (opt.deleteTemplate && tpl.parentNode) {
                    tpl.parentNode.removeChild(tpl);
                }
                text = toInject.call(opt.data, text);
                html = stringParser(text, opt.data);
                back = opt.onReady.call($this, html);
                if (back) {
                    html = back;
                    back = null;
                }
                $.when($this.html(html).promise()).done(function(){
                    opt.onDone.call($this);
                });
            });
        }
    }
        
    /* 
     * 解析指令字符串
     * str：待解析字符串
     * data：原始数据源 
     * scope：经过过滤的数据源(data中的子集)。如指令的条件值已*开头，取scope为数据源
     * return String
     */
    function stringParser(str, data, scope) {
        var selfClosing = false;
        var match, m1, tag, signal, condition;
        var openTag, closeTag, gtTag;
        var _str, _tmp, html = '';
        match = regHasCmd.exec(str);
        if (!match) {
            str = runClass(str, data, scope);
            return str;
        }
        var _tmp1 = str.indexOf(match[0]);
        html += str.slice(0, _tmp1);
        _str = str.slice(_tmp1);
        _tmp1 = null;
        if (san.tools.trim(html)) {
            html = runClass(html, data, scope);
        }
        if (!isSelfClosing(match[1])) {
            match = regCmdTags.exec(_str);
        }
        m1 = match[0];
        tag = match[1];
        signal = match[3];
        condition = match[4];
        if (/^\*/im.test(condition)) {
            condition = condition.slice(1);
            if (scope) {
                data = scope;
                scope = null;
            }
        } else if (/in\s+\*/im.test(condition)) {
            condition = condition.replace(/in\s+\*/im, 'in ');
            if (scope) {
                data = scope;
                scope = null;
            }
        }
        openTag = '<' + tag;
        closeTag = '</' + tag + '>';
        gtTag = '>';
        var index, 
            i = 0,
            _m1 = m1, 
            a = [];

        selfClosing = isSelfClosing(tag);
        if (!selfClosing) {
            do {
                index = _m1.indexOf(openTag);
                if (~index && index < _m1.indexOf(closeTag)) {
                    if (i !== 0) {
                        _tmp = _m1.slice(0, index);
                        a.push(_tmp); 
                        _m1 = _m1.slice(index);
                        _str = strMinus(_str, _tmp);
                    }
                    index = _m1.indexOf(gtTag) + 1;
                    _tmp = _m1.slice(0, index);
                    a.push(_tmp); 
                    _m1 = _m1.slice(index);
                    _str = strMinus(_str, _tmp);
                    i++;
                } else {
                    index = _m1.indexOf(closeTag);
                    _tmp = _m1.slice(0, index);
                    a.push(_tmp); 
                    a.push(closeTag);
                    _m1 = _m1.slice(index + closeTag.length);
                    _str = strMinus(_str, _tmp + closeTag);
                    i--;
                };
            } while (i);
            if (signal === '*san-if') {
                html += runIf(condition, a, data);
            }
            if (signal === '*san-for') {
                html += runFor(condition, a, data);
            }
        } 
        if (selfClosing) {
            if (signal === '*san-if') {
                html += runIf(condition, [m1], data);
            }
            if (signal === '*san-for') {
                html += runFor(condition, [m1], data);
            }
            _str = strMinus(_str, m1);
        }
        if (san.tools.trim(_str)) {
            html += stringParser(_str, data, scope);
        }
        return html;
    }

    function fixed(text) {
        text = text.replace(/^\s*/, '');
        return text;
    }

    /* 
     * 截取字符串并返回
     */
    function strMinus(str, target) {
        return str.slice(str.indexOf(target) + target.length);
    }

    /* 
     * 条件指令san-if解析
     * condition：指令条件
     *            普通：value || key.name
     *            数组：array#index, array#index.name
     *            代码：value.length
     *            三元：a ? b : c。仅支持一层。
     * tags：字符串集合，Array
     * data：数据源 
     * return String
     * */
    function runIf(condition, tags, data) {
        var val, ternary;
        var reverse = false;
        if (ternary = /([^\?:]+)\?([^\?:]+):([^\?:]+)/im.exec(condition)) {
            var _cons = san.tools.trim(ternary[1]);
            if (~_cons.indexOf('.length')) {
                _cons = runLength(_cons, data);
            } else {
                _cons = getValue(_cons, data);
            }
            if (_cons) {
                condition = san.tools.trim(ternary[2]);
            } else {
                condition = san.tools.trim(ternary[3]);
            }
        }
        if (~condition.indexOf('.length')) {
            val = runLength(condition, data);
        } else {
            if (/^!/im.test(condition)) {
                reverse = true;
                condition = condition.slice(1);
            }
            val = getValue(condition, data);
        }
        var html = '';
        if (!reverse && val || reverse && !val) {
            var startTag = '', closeTag = '', rest = '';
            if (tags.length == 1){
                startTag = tags[0];
            } else {
                startTag = tags.shift();
                closeTag = tags.pop();
                rest = tags.join('');
            }
            startTag = runClass(startTag, data);
            if (san.tools.trim(rest)) {
                if (hasCmd(rest)) {
                    rest = stringParser(rest, data);
                } else {
                    rest = runClass(rest, data);
                }
            }
            startTag = clearCmd('san-if', startTag);
            html += startTag + rest + closeTag;
        }
        return html;
    }

    /* 
     * 循环指令san-for解析
     * condition：指令条件。格式： [item] in [records](index)
     *            item：表示集合中的单条记录，自定义，用于插值替换时的标记，如{{#item.url}}、{{#item2.url}}
     *            records格式：
     *                   普通：value || obj.value
     *                   数组：array#index, array#index.name, obj.array#index
     *                   代码：array.length
     *            (index)指定records的索引值范围：值(min[, max]) || (even) || (odd)
     * tags：字符串集合，Array
     * data：数据源 
     * return String
     */
    function runFor(condition, tags, data) {
        var html = '';
        var cons = condition.split('in');
        cons[0] = san.tools.trim(cons[0]);
        cons[1] = san.tools.trim(cons[1]);
        var consMatch, forCons, max = -1, min = 0;
        if (consMatch = /([\d\D]+)\(([^\)]+)\)/im.exec(cons[1])) {
            cons[1] = consMatch[1];
            forCons = consMatch[2].split(',');
            min = parseInt(forCons[0]) || 0;
            if (forCons.length == 2) {
                max = parseInt(forCons[1]) || 0;
            }
        }
        var val = getValue(cons[1], data);
        if (!val) {
            return html;
        }
        var for_i, for_len = val.length;
        var startTag = '', closeTag = '', rest = '';
        if (tags.length === 1){
            startTag = tags[0];
        } else {
            startTag = tags.shift();
            closeTag = tags.pop();
            rest = tags.join('');
        }
        if (max < min || !~max) {max = for_len;}
        for (for_i = 0; for_i < for_len; for_i++) {
            if (forCons && forCons.join('') === 'even' && !san.tools.isEven(for_i)) {
                continue;
            } else if (forCons && forCons.join('') === 'odd' && san.tools.isEven(for_i)) {
                continue;
            } else if (for_i < min || for_i > max) {
                continue;
            }
            var _data = val[for_i];
            var _startTag = startTag,
                _rest = rest;
            var _match = hasCmd(rest);
            if (_match && startTag && closeTag) {
                _rest = stringParser(rest, data, _data);
            } else {
                _rest = runClass(_rest, data, _data, for_i);
            }
            _startTag = runClass(_startTag, data, _data, for_i);
            _startTag = clearCmd('san-for', _startTag);
            html += toInject.call(_data, (_startTag + _rest + closeTag), cons[0], for_i);
        }
        return html;
    }

    /* 
     * 插值替换
     * str：待替换的字符串
     * mark：特定格式的替换对象
     *       特定格式：
     *           {{#item.属性[.属性]}}
     *           {{#item.#index}}：#index：当前记录索引值。为防止与属性index冲突，添加前缀#已区分
     *           item与指令字符串*san-for="item in records"中的item相对应
     */
    function toInject(str, mark, index) {
        var self = this;
        var regTarget;
        if (mark) {
            regTarget = new RegExp('\{\{#' + mark + '.([^(\}\})]*)\}\}', 'g');
        } else {
            regTarget = new RegExp('\{\{([^(#|\}\})]*)\}\}', 'g');
        }
        str = str.replace(regTarget, function(m, $1){
            var a, len;
            var s;
            if (~$1.indexOf('.')) {
                var a = $1.split('.'),
                    len = a.length,
                    i = 0,
                    s = self;
                for (; i < len; i++) {
                    s = s[a[i]];
                }
            } else if ($1 === '#index') {
                s = index;
            } else {
                s = self[$1];
            }
            return (s !== undefined) ? s : m;
        });
        return str;
    }

    /* 
     * 在数据源中查找值
     * str要查找的值
     *      格式：对象属性用.分隔，数组需使用array#index代替array[index]
     * data：数据源 
     * return data中对应的值
     */
    function getValue(str, data) {
        var a = str.split('.');
        var val = data;
        var i, len = a.length;
        for (i = 0; i < len; i++) {
            if (~a[i].indexOf('#')) {
                a[i] = a[i].split('#');
                var _i, _len = a[i].length;
                for (_i = 0; _i < _len; _i++) {
                    val = val[a[i][_i]];
                }
            } else {
                val = val[a[i]];
            }
        }
        return val;
    }

    /* 
     * 执行条件值中的.length
     * .length必须在最后，代码执行对象必须是数组，否则原样返回
     */
    function runLength(str, data) {
        var cons, val;
        cons = str.slice(0, str.indexOf('.length'));
        val = getValue(cons, data);
        if (san.tools.type(val) === 'array'){
            val = val.length;
        }
        return val;
    }

    /* 
     * 样式类指令san-class解析
     * str：待解析字符串。对象：{class名：条件值}
     *      条件值格式：
     *                 普通：value || obj.value
     *                 取反：!value || !obj.value
     * data：数据源 
     * scope：非必需，经过过滤的数据源（data的子集）。指令的条件值已*开头，取scope为数据源
     * index: 非必需，san-for循环指令的索引值。（带不带*均可，index即循环指令结果集的索引值）
     *        格式：
     *              #index：取索引值，即条件永远是true
     *              #index.odd： 索引值为奇数时条件成立
     *              #index.even：索引值为偶数时条件成立
     * return String
     */
    function runClass(str, data, scope, index) {
        var regClass = /<\w+(?:"[^"]*"|'[^']*'|[^'">])+(\*san\-class=(?:"{([^}"]+)}"|'{([^}']+)}'))(?:"[^"]*"|'[^']*'|[^'">])*>/img,
            regClassValue = /\s+(class="([^"]+)"|class='([^']+)'|class=(\S+))/im;
        if (!regClass.test(str)) {
            return str;
        }
        return str.replace(regClass, function(m, $1, $2){
            var classValue = regClassValue.exec(m),
                classPlus = '';

            var rm = $2.split(','),
                a = [],
                i = 0, len = rm.length;
            for (; i < len; i++) {
                rm[i] = rm[i].split(':');
                a[i] = {
                    'class': san.tools.trim(rm[i][0]),
                    'condition': san.tools.trim(rm[i][1])
                };
            }
            i = 0;
            len = a.length;
            var cons, reverse;
            var _data;
            for (; i < len; i++) {
                _data = data;
                cons = a[i].condition;
                reverse = false;
                if (/^\*/im.test(cons)) {
                    cons = cons.slice(1);
                    if (scope) {
                        _data = scope;
                    }
                }
                if (/^!/im.test(cons)) {
                    reverse = true;
                    cons = cons.slice(1);
                }
                if (/^(#index)/i.test(cons) && typeof index === 'number') {
                    if (typeof index === 'number') {
                        if (cons === '#index.odd') {
                            cons = san.tools.isEven(index);
                        } else if (cons === '#index.even') {
                            cons = !san.tools.isEven(index);
                        }
                    } else {
                        cons = true;
                    }
                } 
                if (typeof cons !== 'boolean') {
                    cons = getValue(cons, _data);
                }
                switch (san.tools.type(cons)) {
                    case 'array':
                        cons = cons.length;
                        break;
                    case 'object':
                        cons = san.tools.isEmptyObject(cons) ? false : true;
                        break;
                    case 'date':
                    case 'function':
                    case 'regexp':
                        cons = false;
                        break;
                    // no default
                }
                if (reverse) {cons = !cons;}
                if (cons) {
                    classPlus += ' ' + a[i]['class'];
                }
            }
            classPlus = classPlus.slice(1);
            if (classValue) {
                if (classPlus) {
                    classPlus = ' ' + classPlus;
                }
                m = clearCmd('san-class', m);
                return m.replace(classValue[1], 'class="' + (classValue[2] || classValue[3] || classValue[4]) + classPlus + '"');
            } else {
                if (classPlus) {
                    return m.replace($1, 'class="' + classPlus + '"');
                } else {
                    return clearCmd('san-class', m);
                }
            }
        });
    }
    
    function isSelfClosing(str){
        return regSelfClosingTag.test(str);
    }

    function hasCmd(str) {
        return regHasCmd.test(str);
    }

    /* 
     * 清除指令字符串
     */
    function clearCmd(cmd, str) {
        var regCmd = new RegExp('\\s+\\*' + cmd + '=(?:"[^"]*"|\'[^\']*\')', 'gi');
        str = str.replace(regCmd, '');
        return str;
    }
    
    $.fn.sanTemplate = function(option) {
        var stringTpl = san.tools.objectCreate(san.widget);
        return stringTpl.init(this, methods, arguments);
    };
})(jQuery, window);



/* 
 * 使用sanTemplate创建列表时，当记录数不足时补空行
 * 该方法适用于下列列表：
 *     .san-list-a
 * total: 要显示的记录总数
 * count：当前记录数
 * return String
 */
function listABlank(total, count) {
    var diff = 0, i, str = '', classPlus = '';
    if (!count) {
        count = 0;
    }
    if (count < total) {
        diff = total - count;
    }

    for (i = diff; i > 0; i--) {
        if (san.tools.isEven(i)) {
            classPlus = 'even';
        } else {
            classPlus = 'odd';
        }
        str += '<li class="' + classPlus + '">&nbsp;</li>';
    }
    return '' + str;
}



/**
 * sanDroplist
 * 下拉显示列表
 * @author: zhxming
 * 自定义属性：
 * data-toggle="droplist"：显式声明下拉列表组件。
 * data-droplist：组件id。设置于控制柄上。
 * data-droplist-id: 组件id。设置于下拉列表上。
 * data-status：下拉列表状态。
 *      show：显示（此时下拉列表上应有CLASS：san-droplist-open）；
 *      hide：隐藏；
 *      suspend：暂停中（处于打开关闭过程中）。
 */
;(function($, window, undefined){
    'use strict';

    var config = {
        // CLASS，包裹容器
        wrapper: 'san-droplist-group',
        // CLASS，控制柄
        handle: 'san-droplist-handle',
        // CLASS，下拉列表。该CLASS与san-dropdown同时使用均表示下拉列表。
        droplist: 'san-droplist',
        // 选择器，为控制柄指定下拉列表。null时，默认下拉列表紧跟在控制柄后面。
        selector: null,
        // CLASS，下拉列表打开状态。设置于下拉列表上。
        open: 'san-dropdown-open',
        // CLASS，表示下拉列表已上拉方式显示。设置于下拉列表上
        up: 'san-dropdown-up',
        // 下拉列表width。null（默认） || "auto" || number(px)
        // null || 0：根据css定义，"auto"：下拉列表与控制柄同等宽度，number：指定宽度，单位px， 设为0时等同于null值
        width: null,
        // 下拉列表最小宽度。null || number(px)。null时交由css控制。
        minWidth: null,
        // 下拉列表最大高度。null || number(px)。设为null交由css控制。设为0取消最大高度限制
        maxHeight: null,
        offsetTop: null,
        //向左偏移量，默认0
        left:0,
        // slide || pop
        animate: 'slide',
        duration: 200,
        // self || clone。默认self，使用当前DOM中的下拉列表（紧跟在控制柄之后或用selector指定），设为clone，将克隆当前的下拉列表创建一个新的下拉列表（并作为body的子元素）
        dropType: 'self',
        event: 'click',
        mediaListening: false,
        // 回调。初始化完成后执行。
        // this：$handle控制柄
        onInit: function(){},
        // 回调。下拉列表打开时执行。
        // this：$handle控制柄，$droplist；下拉列表
        onOpen: function($droplist){},
        // 回调。关闭时执行。
        onClose: function(){}
    }
    
    var namespace = 'sanDroplist',
        toggle   = '[data-toggle="droplist"]',
        handleMark = 'data-droplist',           // 控制柄标记，作为自定义属性值为组件id
        droplistMark = handleMark + '-id';      // 下拉列表/面板标记，作为自定义属性值为组件id
    var droplistMap = san.tools.objectCreate(null),
        _droplist = null;
    var $mainpage = null;
    
    var methods = {
        /*
         * 初始化
         */
        init: function(option) {
            return this.each(function(){
                var $handle = $(this),
                    opt = null,
                    droplistId = null,
                    $droplist = null,
                    toggle = null;

                droplistId = san.tools.uuid('san-droplist-');
                $handle.attr(handleMark, droplistId);

                $mainpage = $(TOP_DIV);

                if (option === 'data-api') {
                    opt = $.extend({}, config, {'droplistId': droplistId});
                    if (toggle !== 'droplist') {
                        $handle.attr('data-toggle', 'droplist');
                    }
                    toggle = 'droplist';
                } else {
                    opt = $.extend({}, config, option, {'droplistId': droplistId});
                    $handle.removeAttr('data-toggle');
                    toggle = null;
                }
                
                if ((V_VW < MEDIA_RULE.M || HASTOUCH) && opt.event == 'hover') {
                    opt.event = 'click';
                }

                $handle.data('options', opt).attr('data-status', 'hide');

                opt.onInit.call($handle);

                if (toggle === 'droplist') {
                    methods.toggle.call($handle);
                } else if (opt.event == 'click') {

                    var isMoving = false, y1, y2,divx2;
                    if (DEFAULT_EVENT == 'touchend') {
                    	$handle.find('.section-card-body').find('.bond-container').each(function(){
                    		var div = $(this).find('.bond-container-left');
                    		divx2 = div.offset().left+div.outerWidth();
                    	});

                    	$handle.off('touchstart touchmove');
                        $handle.on('touchstart.' + namespace, function(e) {
                            isMoving = false;
                            y1 = e.originalEvent.touches[0].pageY;
                            var x1 = e.originalEvent.touches[0].pageX;
                            if(divx2 && divx2<x1){
                            	isMoving = true;
                            }
                        });
                        $handle.on('touchmove.' + namespace, function(e) {
                            y2 = e.originalEvent.touches[0].pageY;
                            if (Math.abs(y2 - y1) > 2){
                                isMoving = true;
                            }
                        });
                    }

                    $handle.off(DEFAULT_EVENT + '.' + namespace).on(DEFAULT_EVENT + '.' + namespace, function(e){
                        if (isMoving || $(e.target).attr('data-role') == 'exclude') {return;}
                        e.preventDefault();
                        methods.toggle.call($handle);
                    });

                } else if (opt.event == 'hover') {
                    $handle.on('mouseenter.' + namespace, function(){
                        methods.show.call($handle);
                    });
                    $handle.on('mouseleave.' + namespace, function(e){
                        var $e = $(e.relatedTarget);
                        if ($e.closest('[' + droplistMark + ']').attr(droplistMark) === droplistId) {return;}
                        methods.hide.call($handle);
                    });
                }
                
            });
        },
        /*
         * 创建下拉列表，并作必要设置
         */
        buildList: function() {
            var $handle = $(this),
                opt = $handle.data('options'),
                droplistId = opt.droplistId,
                dropType = $handle.attr('data-type') || opt.dropType,
                $droplist = null,
                $clone = null;

            droplistMap[droplistId] = san.tools.objectCreate(null);
            droplistMap[droplistId]['dropId'] = droplistId;
            droplistMap[droplistId]['handle'] = $handle[0];

            if (opt.selector) {
                $droplist = $(opt.selector);
            }
            if (!opt.selector || !$droplist.length) {
                $droplist = $handle.next('.' + opt.droplist);
            }

            if (dropType === 'self') {
                $droplist.attr(droplistMark, droplistId);

                droplistMap[droplistId]['droplistBackup'] = san.tools.objectCreate(null);
                droplistMap[droplistId]['droplistBackup']['class'] = $droplist.attr('class');
                droplistMap[droplistId]['droplistBackup']['style'] = $droplist.attr('style');
            } 

            if (dropType === 'clone') {
                $clone = $droplist.clone(true);
                $droplist.addClass('NONE');
                $droplist.empty();

                droplistMap[droplistId]['dropOrigin'] = $droplist[0];
    
                var _attr = {}, _id = $clone.attr('id');
                _attr[droplistMark] = droplistId;
                if (_id) {
                    _attr['data-for'] = _id;
                    $clone.removeAttr('id');
                }
    
                $clone.attr(_attr).appendTo('body');
                $droplist = $('[' + droplistMark + '="' + droplistId + '"]');
            }

            droplistMap[droplistId]['droplist'] = $droplist[0];

            var _width = opt.width;
            if (san.tools.type(_width) == 'function') {
                _width = (_width)();
            }

            var cssValue = {},
                width = parseInt($droplist.attr('data-width'),10) || _width,
                minWidth = parseInt($droplist.attr('data-min-width'),10) || parseInt(opt.minWidth, 10),
                maxHeight = parseInt($droplist.attr('data-max-height'),10) || parseInt(opt.maxHeight, 10);

            if ($droplist.attr('data-width') === 'auto' || opt.width === 'auto') {
                cssValue = {
                    'width': $handle.outerWidth() + 'px'
                }
            } else if (!isNaN(width)) {
                cssValue = {
                    'width': width + 'px'
                }
            }
            if (!isNaN(minWidth)) {
                if (minWidth !== 0) {
                    cssValue['min-width'] = minWidth + 'px';
                } else {
                    cssValue['min-width'] = 0;
                }
            }
            if (!isNaN(maxHeight)) {
                if (maxHeight !== 0) {
                    cssValue['max-height'] = maxHeight + 'px';
                } else {
                    cssValue['max-height'] = 'none';
                }
            }
            $droplist.css(cssValue);
        },
        /*
         * 切换器
         */
        toggle: function(callShow, callHide) {
            return this.each(function(){
                var $handle = $(this),
                    droplistId = $handle.attr(handleMark),
                    status = $handle.attr('data-status'),
                    $droplist = null;
                
                if (status === 'hide') {
                    if (!droplistMap[droplistId]) {
                        methods.buildList.call($handle);
                        $droplist = getDroplist(droplistId);
                    }
                    methods.show.call($handle, callShow);
                } else {
                    $droplist = getDroplist(droplistId);
                    methods.hide.call($handle, callHide);
                }

            });
        },
        /*
         * 显示下拉列表
         */
        show: function(fn) {
            return this.each(function(){
                var $handle = $(this),
                    opt = $handle.data('options'),
                    droplistId = opt.droplistId,
                    $droplist = getDroplist(droplistId);
                    
                if ($handle.attr('data-status') === 'suspend' || $handle.attr('data-status') === 'show') {return;}

                if (!$droplist) {
                    methods.buildList.call($handle);
                    $droplist = getDroplist(droplistId);
                }
                
                $handle.attr('data-status', 'suspend');

                methods.clear.call($handle);

                var _dropPanel = san.tools.objectCreate(san.dropdown);

                droplistMap[droplistId]['dropPanel'] = _dropPanel;
                _dropPanel.init($droplist, $handle, {
                    'handleMark': handleMark,
                    'dropPanelMark': droplistMark,
                    'open': opt.open,
                    'up': opt.up,
                    'offsetTop': opt.offsetTop,
                    'dropType': $handle.attr('data-type') || opt.dropType,
                    'animate': $handle.attr('data-animate') || opt.animate,
                    'duration': $handle.attr('data-duration') || opt.animate,
                    'mediaListening': opt.mediaListening,
                    'left':opt.left
                });
                _dropPanel.open();
                if (!opt.mediaListening || V_VW >= MEDIA_RULE.M) {
                    _dropPanel.position();
                }
                
                $.when(_dropPanel.dropIn()).done(function(){
                    $handle.attr('data-status', 'show');

                    _dropPanel = null;

                    if (opt.event == 'hover') {
                        $droplist.off('mouseleave.' + namespace).on('mouseleave.' + namespace, function(e){
                            var $e = $(e.relatedTarget);
                            if ($e.closest('[' + handleMark + ']').attr(handleMark) === droplistId) {return;}
                            methods.hide.call($handle);
                        });
                    }

                    if (opt.mediaListening && V_VW < MEDIA_RULE.M) {
                        var $maskLayer = $mainpage.nextAll('.san-droplist-modal-layer');
                        $maskLayer.on(DEFAULT_EVENT + '.' + namespace, '.san-droplist-btn-close', function(){
                            methods.hide.call($handle);
                        });
                    }

                    if (fn !== false) {
                        if (san.tools.type(fn) === 'function') {
                            fn.call($handle, $droplist);
                        } else {
                            opt.onOpen.call($handle, $droplist);
                        }
                    }
                });
            });
        },
        /*
         * 隐藏下拉列表
         */
        hide: function(fn) {
            return this.each(function(){
                var $handle = $(this),
                    opt = $handle.data('options'),
                    droplistId = opt.droplistId,
                    dropType = $handle.attr('data-type') || opt.dropType,
                    $droplist = null;

                if ($handle.attr('data-status') === 'suspend' || $handle.attr('data-status') === 'hide') {return;}

                $droplist = getDroplist(droplistId);

                if ($droplist === null) {return;}

                $handle.attr('data-status', 'suspend');

                var _dropPanel = droplistMap[droplistId]['dropPanel'];

                $.when(_dropPanel.dropOut()).done(function(){
                    $handle.attr('data-status', 'hide');

                    _dropPanel.close();
                    _dropPanel = null;

                    if (dropType === 'self') {
                        $droplist.removeAttr(droplistMark);

                        var bkp = droplistMap[droplistId]['droplistBackup'],
                            bkp_class = bkp ? bkp['class'] : null,
                            bkp_style = bkp ? bkp['style'] : null;
                        $droplist.attr('class', bkp_class || '');

                        if (bkp_style) {
                            $droplist.attr('style', bkp_style);
                        } else {
                            $droplist.removeAttr('style');
                        }
                    }

                    if (dropType === 'clone') {
                        // $(droplistMap[droplistId]['dropOrigin']).removeClass('NONE');
                        if (droplistMap[droplistId]) {
                            $(droplistMap[droplistId]['dropOrigin']).html($droplist.html()).removeClass('NONE');
                        }
                        $droplist.remove();
                        $droplist = null;
                    }

                    delete droplistMap[droplistId];

                    if (fn !== false) {
                        if (san.tools.type(fn) === 'function') {
                            fn.call($handle);
                        } else {
                            opt.onClose.call($handle);
                        }
                    }
                });
            });
        },
        /*
         * 关闭（全部）下拉列表
         */
        clear: function() {
            $.each(droplistMap, function(k, v){
                if (v.dropPanel) {
                    methods.hide.call($(v.handle), false);
                }
            });
        },
        /*
         * 销毁下拉列表组件。
         * 组件销毁后，必须重新初始化后才能继续使用
         */
        destroy: function(fn){
            return this.each(function(){
                var $handle = $(this),
                    opt = $handle.data('options'),
                    droplistId = null,
                    dropType = null,
                    $droplist = null;

                if (opt) {
                    droplistId = opt.droplistId;
                    dropType = $handle.attr('data-type') || opt.dropType;
                    $droplist = getDroplist(droplistId);
                }

                $handle.removeAttr(handleMark + ' data-status data-toggle');
                
                if ($droplist) { 
                    if (dropType === 'self') {
                        $droplist.removeAttr(droplistMark);
                        
                        var bkp = droplistMap[droplistId]['droplistBackup'],
                            bkp_class = bkp ? bkp['class'] : null,
                            bkp_style = bkp ? bkp['style'] : null;
                        $droplist.attr('class', bkp_class || '');
                        if (bkp_style) {
                            $droplist.attr('style', bkp_style);
                        } else {
                            $droplist.removeAttr('style');
                        }
                    }

                    if (dropType === 'clone') {
                        $droplist.remove();
                        $(droplistMap[droplistId]['dropOrigin']).removeClass('NONE');
                    }

                    delete droplistMap[droplistId];
                }

                if (fn && san.tools.type(fn) === 'function') {
                    fn.call($handle);
                }
            });
        }
    }

    function getDroplist(dropId) {
        var dropId = droplistMap[dropId];
        return san.tools.type(dropId) === 'object' ? $(dropId['droplist']) : null;
    }

    $.fn.sanDroplist = function(){
        var droplist = san.tools.objectCreate(san.widget);
        return droplist.init(this, methods, arguments);
    };

    var inTimer = null;
    $(window).off('resize.' + namespace).on('resize.' + namespace, san.tools.throttle(function(){
        clearInterval(inTimer);
        inTimer = setInterval(function(){
            if (GLOBE_INIT) {
                clearInterval(inTimer);
                if (RESIZE_IGNORE) {return;}
                methods.clear.call($(this));
            }
        }, 10);
    }, 100));

    $(document).on(DEFAULT_EVENT + '.' + namespace, function(e) {
        var $target = $(e.target);
        if (!$target.closest('[data-role="option"]').length && $target.closest('[' + droplistMark + ']').length) {return;}
        if (GLOBE_INIT && V_VW < MEDIA_RULE.M && $target.hasClass('san-droplist-modal-layer')) {return;}
        methods.clear.call($(this));
    });

    $(document).on(DEFAULT_EVENT + '.' + namespace, toggle, function(e) {
        e.stopPropagation();
        var $this = $(this),
            droplistId = $this.attr(handleMark);
        if (droplistId) {
            $this.sanDroplist('toggle');
            return false;
        }
        $this.sanDroplist('init', 'data-api');
    });
    
    /*
     * 下拉面板
     */
    san.dropdown = {
        option: {
            'handleMark': handleMark,
            'dropPanelMark': droplistMark,
            'wrapper': config.wrapper,
            'open': config.open,
            'up': config.up,
            'offsetTop': config.offsetTop,
            'animate': config.animate,
            'duration': config.duration,
            'dropType': config.dropType
        }, 
        init: function($droplist, $handle, option) {
            this.$handle = $handle;
            this.$droplist = $droplist;
            this.option = $.extend({}, this.option, option);
            this.dropId = $droplist.attr(this.option.dropPanelMark);
            this.$wrapper = $handle.hasClass(this.option.wrapper) ? null : $handle.closest('.' + this.option.wrapper);
        },
        open: function() {
            this.$droplist.addClass(this.option.open);
        },
        opened: function() {
            return this.$droplist.hasClass(this.option.open);
        }, 
        close: function() {
            var $droplist = this.$droplist,
                opt = this.option,
                animate = opt.animate;

            $droplist.removeClass(opt.open + ' OH');

            if (animate === 'slide') {
                $droplist.css('height', '');
                // $droplist.css({
                //     'height': 'auto'
                // });
            }
            if (animate === 'pop') {
                $droplist.removeClass('san-dropdown-pop-out');
            }
        }, 
        position: function() {
            var $droplist = this.$droplist,
                $handle = this.$handle,
                $wrapper = this.$wrapper,
                opt = this.option,
                vh = V_VH,
                handleRect = san.view.rect($handle[0]),
                handleTop = Math.round(handleRect.top),
                handleBottom = Math.round(handleRect.bottom),
                handleHeight = Math.round(handleRect.height),
                dropHeight = 0,
                handleOffset = san.view.offset($handle[0]),
                wrapperOffset = $wrapper ? san.view.offset($wrapper[0]) : handleOffset,
                offsetTop = opt.offsetTop;

            if (!this.opened()) {return false;}
            
            dropHeight = $droplist.outerHeight(true);

            $droplist.removeClass(opt.up);

            if (offsetTop) {
                if (san.tools.type(offsetTop) == 'function') {
                    offsetTop = offsetTop();
                }
            } else {
                offsetTop = 0;
            }

            if (opt.dropType === 'clone') {
                var left;
                if ($droplist.hasClass('san-dropdown-right')) {
                    left = wrapperOffset.left + handleRect.width - $droplist.outerWidth()-opt.left;
                } else {
                    left = wrapperOffset.left-opt.left;
                }
                $droplist.css({
                    'top': handleOffset.top + handleHeight + 'px',
                    'bottom': 'auto',
                    'left': left  + 'px'
                });
            }
        },
        dropIn: function() {
            var $droplist = this.$droplist,
                $handle = this.$handle,
                opt = this.option,
                animate = opt.animate,
                duration = opt.duration,
                dropHeight = $droplist.outerHeight(), 
                $dtd = $.Deferred();

            if (opt.mediaListening && V_VW < MEDIA_RULE.M) {
                this.popup();
                setTimeout(function(){
                    $dtd.resolve();
                }, 100);
            } else {
                if (animate === 'slide' && (!~IE_V || IE_V > 9)) {
                    $droplist.addClass('OH').css({
                        'height': 0
                    });
                }

                setTimeout(function(){
                    $droplist.addClass('san-dropdown-slide').css({
                        'height': dropHeight + 'px',
                        'transition-duration': duration + 'ms, 100ms'
                    });
                    setTimeout(function(){
                        $droplist.removeClass('OH');
                        $dtd.resolve();
                    }, 100);
                },10);
            }

            return $dtd.promise();
        },
        dropOut: function() {
            var $droplist = this.$droplist,
                $handle = this.$handle,
                opt = this.option,
                animate = opt.animate,
                duration = opt.duration,
                $dtd = $.Deferred();

            if (opt.mediaListening && V_VW < MEDIA_RULE.M) {
                var $maskLayer = $mainpage.nextAll('.san-droplist-modal-layer'),
                    $modal = $maskLayer.children('.san-droplist-modal'),
                    $close = $maskLayer.children('.san-droplist-btn-close');
                $close.remove();
                $modal.removeClass('san-droplist-modal-pop-in').addClass('san-droplist-modal-pop-out');
                var top = Math.abs(parseInt($mainpage.css('top')));
                $mainpage.css('top', '').removeClass('masked');
                $('html, body').scrollTop(top);
                setTimeout(function(){
                    $mainpage.nextAll('.san-droplist-modal-layer').remove();
                    $dtd.resolve();
                }, 100);
            } else {
                setTimeout(function(){
                    $mainpage.css('top', '').removeClass('masked');
                    if (~IE_V && IE_V < 10) {
                        $droplist.removeClass('san-dropdown-slide');
                    } else {
                        $droplist.addClass('OH').css({
                            'height': 0
                        }).removeClass('san-dropdown-slide');
                    }
                    setTimeout(function(){
                        $mainpage.nextAll('.san-droplist-modal-layer').remove();
                        $dtd.resolve();
                    }, 100);
                }, 10);
            }

            return $dtd.promise();
        },
        popup: function(){
            var $droplist = this.$droplist,
                $handle = this.$handle,
                $wrapper = this.$wrapper,
                opt = this.option,
                $maskLayer = null,
                $modal = null,
                $close = null,
                $dtd = $.Deferred();

            $mainpage.css('top', '-' + san.view.scroll().top + 'px').addClass('masked');

            $droplist.css({'width': '', 'height': ''}).wrap('<div class="san-droplist-modal-layer"><div class="san-droplist-modal"></div></div>');
            $maskLayer = $mainpage.nextAll('.san-droplist-modal-layer');
            $modal = $maskLayer.children('.san-droplist-modal');
            $maskLayer.append('<a class="san-droplist-btn-close" href="javascript:void(0);"></a>');
            $close = $maskLayer.children('.san-droplist-btn-close');

            setTimeout(function(){
                $modal.css('margin-top', (V_VH - $modal.outerHeight() - $close.outerHeight(true)) * 0.5).addClass('san-droplist-modal-pop-in');
                $close.addClass('active');
            }, 300);
        }
    }

})(jQuery, window);



/**
 * sanTooltips
 * @author: zhxming
 * 提示贴。
 */
;(function($, san, window, undefined){
    'use strict';

    var config = {
        // CLASS，提示贴容器
        tips: 'san-tooltips',
        // CLASS，提示贴的激活状态
        tipsActive: 'san-tooltips-active',
        // CLASS，提示贴的内容容器
        tipsContent: 'san-tooltips-inner',
        classPlus: null,
        // 悬浮内容层显示位置。'bottom || top || right || left'
        tipsAt: 'bottom',
        // 显示位置对齐方式。 'center(默认) || start || end'。
        tipsAlign: 'center',
        // 显示位置偏移量。单位px。默认偏移量为内容容器的内边距（参见css）
        tipsOffset: 10,
        // 指向器。值：CLASS(String)或false(Boolean)。设为false，不显示指向器
        tipsArrow: 'san-tooltips-arrow',
        // 指向器大小。与CSS的设置向对应。（在能计算大小的场景下，该值无效。）
        tipsArrowSize: 16,
        // 指向器偏移量。与CSS的设置向对应。
        tipsArrowOffset: 12,
        // 宽度。单位px。不支持'auto'。
        width: null,
        // 显示延时。毫秒
        delay: 0,
        // 显示时带动画效果（fadein）。true || false。
        animate: true,
        // CLASS，提示贴的动画状态
        animateClass: 'san-tooltips-animate',
        // 显示动画效果持续时间，与CSS对应。毫秒
        duration: 100,
        // 是否在iframe中显示。Boolean。
        // true：在iframe自身中显示
        // false：默认。在最顶层document内显示
        inIframe: false,
        // 内容类型。
        // 'text' - （默认）文本或简单html。优先从自定义属性data-text获取。
        // 'html' - 本地html内容。
        // 'load' - 远程html内容。使用ajax加载文档片段。优先从自定义属性data-url获取。
        // 'json' - 远程json。需要使用回调方法dataHandler将规整后要显示的内容返回。
        type: 'html',
        // 要显示的文本或简单html。type='text'时有效。当自定义属性data-text存在时优先从data-text获取内容。
        text : null,
        // 选择器表达式。仅type='html'时有效。用于在页面中获取指定html内容。
        // 注意selector指向的元素的唯一性。
        selector:  null,
        // 要加载的文档的链接地址。type='load||json'时有效。优先从自定义属性data-url获取值。
        url: null,
        // type='load||json'时有效
        loadMethod: 'GET',
        // type='load'时有效
        cache: true,
        // 是否为URL添加时间戳，type='load'时有效。
        timestamp: true,
        // 加载时的提示信息。type='load||json'时有效。文本或简单html。
        loadingText: '<div>正在加载，请稍候……</div>',
        // 加载失败时的提示信息。type='load||json'时有效。文本或简单html。
        loadedFailText: '<div>加载失败！请稍后重试。</div>', 
        // 注入替换。 type='load'时有效。true || false。详见sanJumpto
        inject: true,
        // 注入替换对象。type='load'时有效。提供名值对。详见sanJumpto
        injectObj: {},
        // 初始化完成后执行。$tips - （jQuery对象）提示贴
        onInit: function(){},
        // 显示后执行。$tips - （jQuery对象）提示贴
        onShow: function($tips){},
        // 关闭后执行。$tips - （jQuery对象）提示贴
        onHide: function(){},
        // type='load'时有效。加载成功后执行。$tips - （jQuery对象）提示贴
        onDone: function($tips){},
        // type='load'时有效。加载失败后执行。$tips - （jQuery对象）提示贴
        onFail: function($tips){},
        // 当type='json'时有效。通过此回调方法从返回的json数据中提取规整要显示的内容。
        // 需要return数据;
        dataHandler: function(){}
    }

    var toggle = '[data-toggle="tooltips"]',
        namespace = 'sanTooltips',
        clearTime = null,
        showTimeout = null,
        ws = window.self, 
        wt = window.top,
        $mainpage;

    var methods = {
        /*
         * 初始化
         * this: 控制柄
         */
        init: function(option){
            return this.each(function(){
                var $this = $(this),
                    tipsId,
                    opt,
                    toggle = $this.attr('data-toggle');

                tipsId = san.tools.uuid('san-tooltips-');
                $this.attr('data-tooltips', tipsId);

                if (option === 'data-api') {
                    opt = $.extend({}, config, {'tipsId': tipsId});
                    if (toggle !== 'tooltips') {
                        $handle.attr('data-toggle', 'tooltips');
                    }
                } else {
                    opt = $.extend({}, config, {'tipsId': tipsId}, option);
                    $this.removeAttr('data-toggle');
                    toggle = null;
                }
                
                $mainpage = $(TOP_DIV);

                $this.data('options', opt);

                var _animate = $this.attr('data-animate') || opt.animate,
                    _delay = parseInt($this.attr('data-delay') || opt.delay, 10);
                
                _animate = _animate ? (_animate === 'false') ? false : true : false;
                _delay = isNaN(_delay) ? 0 : _delay;

                // methods.buildTips.call($this, _animate);
                
                opt.onInit.call($this);
                
                if (toggle !== 'tooltips') {
                    var event = V_VW < MEDIA_RULE.M ? DEFAULT_EVENT : 'mouseenter';
                    $this.off(event + '.' + namespace).on(event + '.' + namespace, function(e){
                        // if ($('#' + tipsId).length) {return false;}
                        clearTimeout(clearTime);
                        clearTime = setTimeout(function(){
                            methods.show.call($this, _animate);
                        }, _delay);
                    });
                } else {
                    clearTimeout(clearTime);
                    clearTime = setTimeout(function(){
                        methods.show.call($this, _animate);
                    }, _delay);
                }
                
                $this.off('mouseleave.' + namespace).on('mouseleave.' + namespace, function(e){
                    clearTimeout(clearTime);
                    if (V_VW < MEDIA_RULE.M) {return false;}
                    if (!e.relatedTarget) {return false;}
                    var $e = $(e.relatedTarget),
                        $_tips = $e.closest('.' + opt.tips);
                    if ($_tips.length && $_tips[0].id == tipsId) {return false;}
                    methods.hide.call($this, _animate);
                });
            });
        },
        /*
         * 创建提示贴
         * this：控制柄（jQuery）
         * animate: Boolean，是否执行动画，可选，默认true
         */
        buildTips: function(animate){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    tipsId = opt.tipsId,
                    tipsArrow = opt.tipsArrow,
                    _animate = animate === false ? false : true,
                    strTips = '';

                strTips += '<div class="' + (_animate ? opt.tips + ' ' + opt.animateClass : opt.tips) + '" id="' + tipsId + '" data-status="ready">';
                if (tipsArrow && typeof tipsArrow == 'string') {
                    strTips += '<div class="' + tipsArrow + '"></div>';
                }
                strTips += '<div class="' + opt.tipsContent + '">';
                strTips += '</div>';
                strTips += '</div>';
                
                if (opt.inIframe) {
                    $('body').append(strTips);
                } else {
                    $(wt.document.body).append(strTips);
                }
            });
        },
        /*
         * 显示tooltips
         * this：控制柄
         * animate: Boolean，是否执行动画，可选，默认true
         */
        show: function(animate){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    tipsId = opt.tipsId,
                    _type = $this.attr('data-type') || opt.type,
                    $tips = null,
                    $content = null,
                    status = '',
                    _animate = animate === false ? false : true,
                    dura = Math.max(0, _animate ? (parseInt($this.attr('data-duration')|| opt.duration, 10)) : 0);

                clearTimeout(showTimeout);
                
                methods.buildTips.call($this, _animate);

                $tips = $('#'+ tipsId);
                if (opt.classPlus) {
                    $tips.addClass(opt.classPlus);
                }
                if (!opt.inIframe && ws != wt) {
                    $tips = $(wt.document.getElementById(tipsId));
                }
                  
                $content = $tips.find('.' + opt.tipsContent);
                status = $tips.attr('data-status');

                if (_type === 'text'){
                    if (status !== 'done') {
                        $content.html($this.attr('data-text') || opt.text);
                        status = 'done';
                        $tips.attr('data-status', status);
                    }
                    methods.position.call($this);
                    $tips.addClass(opt.tipsActive);

                    showTimeout = setTimeout(function() {
                        opt.onShow.call($this, $tips);
                    }, dura);
                }

                if (_type === 'html'){
                    if (status !== 'done') {
                        var selector = $this.attr('data-target') || opt.selector;
                        $content.html($(selector).html());
                        status = 'done';
                        $tips.attr('data-status', status);
                    }
                    methods.position.call($this);
                    $tips.addClass(opt.tipsActive);

                    showTimeout = setTimeout(function() {
                        opt.onShow.call($this, $tips);
                    }, dura);

                    // $tips.fadeIn(dura, function(){
                    //     opt.onShow.call($this, $tips);
                    // });
                }

                if (_type === 'load'){
                    // ...
                }

                if (_type == 'json') {
                    // ...
                }
                
                $tips.off('mouseleave.' + namespace).on('mouseleave.' + namespace, function(e){
                    clearTimeout(clearTime);
                    if (V_VW < MEDIA_RULE.M) {return false;}
                    var $e = $(e.relatedTarget);
                    if ($e.closest('[data-tooltips="' + tipsId + '"]').length){return false;}
                    methods.hide.call($this);
                });
            });
        },
        /*
         * 隐藏tooltips
         * this：控制柄
         * animate: Boolean，是否执行动画，可选，默认true
         */
        hide: function(animate){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    tipsId = opt.tipsId,
                    $tips = null,
                    tipsClass = opt.tips,
                    _animate = animate === undefined ? true : animate,
                    dura = Math.max(0, _animate ? (parseInt($this.attr('data-duration') || opt.duration, 10)) : 0);

                clearTimeout(showTimeout);

                $tips = $('#'+ tipsId);
                if (!opt.inIframe && ws != wt) {
                    $tips = $(wt.document.getElementById(tipsId));
                }

                if ($tips.attr('data-modal')) {
                    var top = Math.abs(parseInt($mainpage.css('top')));
                    $mainpage.css('top', '').removeClass('masked');
                    $('html, body').scrollTop(top);
                }

                $tips.remove();

                opt.onHide.call($this);
            });
        },
        /*
         * 定位tooltips
         * this：控制柄
         */
        position: function(){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    tipsId = opt.tipsId,
                    $tips = null,
                    $arrow = null,
                    tipsClass = opt.tips,
                    tipsContent = opt.tipsContent;

                $tips = $('#'+ tipsId);
                if (!opt.inIframe && ws != wt) {
                    $tips = $(wt.document.getElementById(tipsId));
                }
                
                if (V_VW < MEDIA_RULE.M) {
                    methods.popup.call($this, $tips);
                    return;
                }

                $arrow = $tips.find('.' + opt.tipsArrow);
                
                var vw = document.documentElement.clientWidth,
                    vh = V_VH,
                    docw = san.view.document().width,
                    // handleRect = $this[0].getBoundingClientRect(),
                    handleRect = san.view.rect($this[0]),
                    handleTop = handleRect.top,
                    handleBottom = handleRect.bottom,
                    handleLeft = handleRect.left,
                    handleRight = handleRect.right,
                    handleWidth = handleRect.width,
                    handleHeight = handleRect.height,
                    posTop = parseFloat($this.offset().top),
                    posLeft =  parseFloat($this.offset().left),
                    tipsWidth = parseFloat($tips.outerWidth(true)),
                    tipsHeight = parseFloat($tips.outerHeight(true)),
                    tipsTop = 0,
                    tipsLeft = 0,
                    hasArrow = ($arrow.length) ? true : false,
                    arrowSize = (hasArrow) ? (parseFloat(opt.tipsArrowSize) || 0) : 0,
                    arrowTop = 0,
                    arrowLeft = 0,
                    arrowOffset = (hasArrow) ? (parseFloat(opt.tipsArrowOffset) || 0) : 0,
                    // 显示方位，显示位置类型，显示偏移量
                    _at = $this.attr('data-placement') || opt.tipsAt,
                    _align = $this.attr('data-align') || opt.tipsAlign,
                    _offset = parseFloat($this.attr('data-align-offset') || opt.tipsOffset) || 0,
                    _width = parseFloat($this.attr('data-width') || opt.width);

                // 视域小于文档宽度，以文档宽度为基准
                if (vw < docw) {
                    vw = docw;
                    handleLeft = posLeft;
                    handleRight = posLeft + handleWidth;
                }

                // 控制柄在iframe内，但提示贴在最外层
                if (!opt.inIframe && ws != wt) {
                    vw = wt.document.documentElement.clientWidth;
                    vh = wt.innerHeight,
                    handleTop = handleRect.top;
                    handleBottom = handleRect.bottom;
                    handleLeft = handleRect.left;
                    handleRight = handleRect.right;
                    posTop = parseFloat($this.offset().top);
                    posLeft = parseFloat($this.offset().left);
                }
                
                // 设置指定width
                if (!!_width){
                    $tips.find('.' + tipsContent).css({
                        'width': _width + 'px'
                    });
                    tipsWidth = parseFloat($tips.outerWidth(true));
                    tipsHeight = parseFloat($tips.outerHeight(true));
                }

                // 修正width
                if ($tips.find('.' + tipsContent).width() > vw * 0.7) {
                    _width = vw * 0.7;
                    $tips.find('.' + tipsContent).css({
                        'width': _width + 'px'
                    });
                    tipsWidth = parseFloat($tips.outerWidth(true));
                    tipsHeight = parseFloat($tips.outerHeight(true));
                }
                
                // 小屏幕适配设置
                if (Math.max(vw, docw) < MEDIA_RULE.M) {
                    if (_at == 'left' || _at == 'right') {
                        _at = 'bottom';
                    }
                    if (handleLeft + handleWidth * 0.5 < tipsWidth * 0.5) {
                        _align = 'start';
                    } else if (vw - handleLeft - handleWidth * 0.5 < tipsWidth * 0.5) {
                        _align = 'end';
                    } else {
                        _align = 'center';
                    }
                }
                   
                // 上方和下方显示时
                if (_at == 'top' || _at == 'bottom'){
                    if (_at == 'bottom'){
                        $tips.addClass(tipsClass + '-bottom');
                        tipsHeight = parseFloat($tips.outerHeight(true));
                        tipsTop = posTop + handleHeight;
                    }
                    if (_at == 'top'){
                        $tips.addClass(tipsClass + '-top');
                        tipsHeight = parseFloat($tips.outerHeight(true));
                        tipsTop = posTop - tipsHeight;
                    }
                   
                    arrowSize = (hasArrow) ? ($arrow.outerWidth() || parseFloat(opt.tipsArrowSize) || 0) : 0;
                    
                    // 获取x坐标，定位指向器
                    switch(_align){
                        case 'center':
                            tbCenter();
                            break;
                        case 'start':
                            tbStart();
                            break;
                        case 'end':
                            tbEnd();
                            break;
                        // no default
                    }
                }

                // 居中对齐
                function tbCenter() {
                    tipsLeft = posLeft + handleWidth * 0.5 - tipsWidth * 0.5;
                    $arrow.removeAttr('style');
                }

                // 居右边界对齐
                function tbEnd() {
                    // 修正偏移量
                    if (tipsWidth >= handleWidth){
                        if (_offset > (tipsWidth - handleWidth)) {
                            _offset = tipsWidth - handleWidth;
                        }
                    }else{
                        if (_offset > (tipsWidth - arrowSize)) {
                            _offset = tipsWidth - arrowSize;
                        }
                    }
                    arrowLeft = tipsWidth - arrowOffset - _offset;
                    tipsLeft = handleRight - tipsWidth + _offset;
                    $arrow.css('left',  arrowLeft + 'px');
                }

                // 居左边界对齐
                function tbStart() {
                    // 修正偏移量
                    if (tipsWidth >= handleWidth){
                        if (_offset > (tipsWidth - handleWidth)) {
                            _offset = tipsWidth - handleWidth;
                        }
                    }else{
                        if (_offset > (tipsWidth - arrowSize)) {
                            _offset = tipsWidth - arrowSize;
                        }
                    }
                    arrowLeft = arrowOffset + _offset;
                    tipsLeft = handleLeft - _offset;
                    $arrow.css('left',  arrowLeft + 'px');
                }

                // 在左侧和右侧显示时
                if (_at == 'left' || _at == 'right'){
                    if (_at == 'right'){
                        $tips.addClass(tipsClass + '-right');
                        tipsWidth = parseFloat($tips.outerWidth(true));
                        tipsLeft = posLeft + handleWidth;
                    }
                    if (_at == 'left'){
                        $tips.addClass(tipsClass + '-left');
                        tipsWidth = parseFloat($tips.outerWidth(true));
                        tipsLeft = posLeft - tipsWidth;
                    }
                   
                    arrowSize = (hasArrow) ? ($arrow.outerHeight() || parseFloat(opt.tipsArrowSize) || 0) : 0;
                    
                    switch(_align){
                        case 'center':
                            lrCenter();
                            break;
                        case 'start':
                            lrStart();
                            break;
                        case 'end':
                            lrEnd();
                            break;
                        // no default;
                    }
                }

                // 居中对齐
                function lrCenter() {
                    tipsTop = posTop + handleHeight * 0.5 - tipsHeight * 0.5;
                    $arrow.removeAttr('style');
                }

                // 居顶部边界对齐
                function lrStart() {
                    if (tipsHeight > handleHeight){
                        if (_offset > (tipsHeight - handleHeight)) {
                            _offset = tipsHeight - handleHeight;
                        }
                    }else{
                        if (_offset > (tipsHeight - arrowSize)) {
                            _offset = tipsHeight - arrowSize;
                        }
                    }
                    arrowTop = arrowOffset + _offset
                    tipsTop = posTop - _offset;
                    $arrow.css('top', arrowTop + 'px');
                }

                // 居底部边界对齐
                function lrEnd() {
                    if (tipsHeight > handleHeight){
                        if (_offset > (tipsHeight - handleHeight)) {
                            _offset = tipsHeight - handleHeight;
                        }
                    }else{
                        if (_offset > (tipsHeight - arrowSize)) {
                            _offset = tipsHeight - arrowSize;
                        }
                    }
                    arrowTop = tipsHeight - arrowOffset - _offset;
                    tipsTop = posTop + handleHeight - tipsHeight + _offset;
                    $arrow.css('top', arrowTop + 'px');
                }

                // 定位
                $tips.css({
                    'top': tipsTop + 'px',
                    'left': tipsLeft + 'px'
                });
                
            });
        },
        popup: function($tips){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $inner = $tips.find('.' + opt.tipsContent),
                    $outer = null,
                    $close = null;
                
                $tips.attr('data-modal', 'pop').append('<a class="san-tooltips-btn-close" href="javascript:void(0);"></a>');
                $close = $tips.find('.san-tooltips-btn-close');

                $inner.wrap('<div class="san-tooltips-outer"></div>');
                $outer = $tips.find('.san-tooltips-outer');

                $mainpage.css('top', '-' + san.view.scroll().top + 'px').addClass('masked');

                setTimeout(function(){
                    $outer.css('margin-top', (V_VH - $outer.outerHeight() - $close.outerHeight(true)) * 0.5).addClass('san-tooltips-pop-in');
                    $close.addClass('san-tooltips-pop-in');
                }, 300);

                $close.on(DEFAULT_EVENT + '.' + namespace, function(){
                    $outer.removeClass('san-tooltips-pop-in').addClass('san-tooltips-pop-out');
                    $close.removeClass('san-tooltips-pop-in').addClass('san-tooltips-pop-out');
                    setTimeout(function(){
                        methods.hide.call($this);
                    }, 100);
                });

                var inTimer = null;
                $(window).on('resize.' + namespace, san.tools.throttle(function(){
                    clearInterval(inTimer);
                    inTimer = setInterval(function(){
                        if (GLOBE_INIT) {
                            clearInterval(inTimer);
                            if (RESIZE_IGNORE) {return;}
                            methods.hide.call($this);
                        }
                    }, 10);
                }, 200));
            });
        }
    }

    $.fn.sanTooltips = function(){
        var tooltips = san.tools.objectCreate(san.widget);
        return tooltips.init(this, methods, arguments);
    };
})(jQuery, san, window);



/**
 * sanExpander
 * 折叠面板（手风琴面板）
 * @author: zhxming
 * 自定义属性：
 * data-fold - 内容区上。内容区折叠时=1；展开状态时=0。
 * data-min/max - 内容区上。内容区最小/最大显示尺寸。
 */
;(function($){
    'use strict';

    var config = {
        // 容器，CLASS
        expander: 'san-expander',
        // 内容区，CLASS/id
        // 如果内容区不在容器san-expander内，则传入id
        content: 'san-expander-content',
        // 内容区面板，content的子元素
        panel: 'san-expander-panel',
        // 控制柄，CLASS
        btn: 'san-expander-btn',
        // 控制柄CLASS，表内容区折叠状态
        fold: 'san-expander-fold',
        // 控制柄CLASS，表内容区展开状态
        unfold: 'san-expander-unfold',
        // 控制柄折叠状态时显示的提示文本（title属性）
        foldText: '展开',
        // 控制柄展开状态时显示的提示文本（title属性）
        unfoldText: '收起',
        // 是否默认折叠
        defaultFold: true,
        // 内容区最小显示高度。number，单位px
        min: 0,
        // 内容区最大显示高度。number || null，单位px。null时不限制最大高度。
        max: null,
        // 是否启用动画效果
        animate: true,
        // 动画持续时间。毫秒，animate='true'时有效。
        duration: 200,
        // 自动折叠非当前操作面板。
        // 这些面板必须是同级元素。不执行回调方法。
        autoFold: false,
        // 如要自行绑定控制柄触发事件，将eventBind设为false。一般用于内容区有异步加载的情况。
        eventBind: true,
        // 内容区折叠开始/结束时执行
        onFoldStart: function($content){},
        onFoldEnd: function($content){},
        // 内容区展开开始/结束时执行
        onUnfoldStart: function($content){},
        onUnfoldEnd: function($content){},
        onResize: false
    }

    var namespace = 'sanExpander',
        handleMark = 'data-expander';

    var methods = {
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this),
                    $btn = $this.find('.' + opt.btn + ':eq(0)'),
                    $content = $this.find('.' + opt.content + ':eq(0)');
                
                if ($content.length == 0){
                    $content = $('#' + opt.content);
                };
                
                var expId = san.tools.uuid('san-expander-');
                $this.attr(handleMark, expId);
                $btn.attr(handleMark, expId);
                $content.attr(handleMark, expId);

                opt.min = Math.min(0, opt.min ? parseInt(opt.min, 10) : 0);
                opt.max = Math.max(opt.min, opt.max ? parseInt(opt.max, 10) : 0);
                opt.duration = parseInt(opt.duration, 10);
                $this.data('options', opt);
                
                if (opt.defaultFold){
                    methods.fold.call($this, null, false, false);
                }else{
                    methods.unfold.call($this, null, false, false);
                }

                $this.attr('data-listener', 'media');
                san.listener.duplicated($this[0], MEDIA_LISTENER_GROUP);
                MEDIA_LISTENER_GROUP[expId] = $this[0];

                var waitingTimer;
                $this.off(MEDIA_LISTENER + '.' + namespace).on(MEDIA_LISTENER + '.' + namespace, function() {
                    clearInterval(waitingTimer);
                    waitingTimer = setInterval(function(){
                        if (GLOBE_INIT) {
                            clearInterval(waitingTimer);
                            if (san.tools.type(opt.onResize) == 'function') {
                                methods.calculate.call($this, opt.animte, true, opt.onResize);
                            } else {
                                methods.calculate.call($this, opt.animte, false, false);
                            }
                        }
                    }, 10);
                });

                if (!opt.eventBind){return false;}

                $this.off(DEFAULT_EVENT + '.' + namespace, '.' + opt.btn).on(DEFAULT_EVENT + '.' + namespace, '.' + opt.btn + '[' + handleMark + '="' + expId + '"' + ']', function(){
                    if ($btn.hasClass(opt.fold)){
                        methods.unfold.call($this);
                        if (opt.autoFold){
                            $this.siblings('.' + opt.expander).each(function(){
                                methods.fold.call($(this), null, null, false)
                            });
                        }
                    }else{
                        methods.fold.call($this);
                    }
                });
            });
        },
        /*
         * 折叠内容区
         * 参数：
         * runCalculate - 是否计算内容区尺寸，默认true
         * hasAnimate - 是否运行动画效果，默认true
         * runCallback - 是否执行回调，默认true
         * onStart - Funtion，折叠前执行。参数同config.onFoldStart。
         *           如果存在则将跳过config.onFoldStart而执行onStart。
         * onEnd - Funtion，折叠后执行。将传给calculate()。参数同config.onFoldEnd。
         */
        fold: function(runCalculate, hasAnimate, runCallback, onStart, onEnd){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    expId = $this.attr(handleMark),
                    $btn = $this.find('.' + opt.btn + '[' + handleMark + '=' + expId + ']'),
                    $content = $this.find('.' + opt.content + '[' + handleMark + '=' + expId + ']');

                var calculate = (runCalculate === false) ? false : true,
                    animte = (hasAnimate === false) ? false : true,
                    run = (runCallback === false) ? false : true;

                if ($content.length == 0 || $content.attr('data-fold') == '1'){return;}

                if (run){
                    if (typeof onStart === 'function'){
                        onStart.call($this, $content);
                    }else{
                        opt.onFoldStart.call($this, $content);
                    }
                }
                
                $btn.removeClass(opt.unfold).addClass(opt.fold).attr('title', opt.foldText);
                $content.attr('data-fold', 1);

                if (calculate){
                    methods.calculate.call($this, animte, run, onEnd);
                }
            });
        },
        /*
         * 展开内容区
         * 参数：
         * runCalculate - Boolean，是否计算内容区尺寸，默认true
         * hasAnimate - Boolean，是否运行动画效果，默认true
         * runCallback - Boolean，是否执行回调，默认true
         * onStart - Funtion，展开前执行。参数同config.onUnfoldStart。
         *           如果存在则将跳过config.onUnfoldStart而执行onStart。
         * onEnd - Funtion，展开后执行。将传给calculate()。参数同config.onUnfoldEnd。
         */
        unfold: function(runCalculate, hasAnimate, runCallback, onStart, onEnd){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    expId = $this.attr(handleMark),
                    $btn = $this.find('.' + opt.btn + '[' + handleMark + '=' + expId + ']'),
                    $content = $this.find('.' + opt.content + '[' + handleMark + '=' + expId + ']'),
                    $panel = $content.children();

                var calculate = (runCalculate === false) ? false : true,
                    animte = (hasAnimate === false) ? false : true,
                    run = (runCallback === false) ? false : true;
                
                if ($content.length == 0 || $content.attr('data-fold') == '0'){return;}

                if (run){
                    typeof onStart === 'function' ? onStart.call($this, $content) : opt.onUnfoldStart.call($this, $content);
                }

                $btn.removeClass(opt.fold).addClass(opt.unfold).attr('title', opt.unfoldText);
                $content.attr('data-fold', 0);
                
                if (calculate){
                    methods.calculate.call($this, animte, run, onEnd);
                }
            });
        },
        /*
         * 计算内容区尺寸
         * 参数：
         * hasAnimate - 是否运行动画效果
         * runCallback - 是否执行回调
         * onEnd - Funtion，展开前执行。参数同config.onUnfoldEnd/config.onUFoldEnd。
         *         如果存在则将跳过config.onUnfoldEnd/config.onUFoldEnd而执行onEnd。
         */
        calculate: function(hasAnimate, runCallback, onEnd){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    expId = $this.attr(handleMark),
                    $btn = $this.find('.' + opt.btn + '[' + handleMark + '=' + expId + ']'),
                    $content = $this.find('.' + opt.content + '[' + handleMark + '=' + expId + ']'),
                    $panel = $content.children(),
                    h;

                var animte = (hasAnimate === false) ? false : true,
                    run = (runCallback === false) ? false : true,
                    flag = $content.attr('data-fold');
                
                // var h = (flag == '1') ? $content.attr('data-min') + 'px' : (opt.max) ? opt.max : $content.attr('data-max') ;
                if (flag == '1') {
                    h = opt.min ? opt.min : 0;
                } else {
                    h = opt.max ? opt.max : $panel.outerHeight(true);
                }

                if (opt.animate && animte){
                    $content.animate({'height': h + 'px'}, opt.duration, function(){
                        callThis();
                        // setTimeout(function(){
                        //     $content.css('height', '');
                        // }, 200);
                    });
                    return;
                }

                $content.css('height', h);
                callThis();

                function callThis(){
                    if (!run) {return false;}
                    
                    if (typeof onEnd === 'function'){
                        onEnd.call($this, $content);
                        return false;
                    }
                    if (flag == '0'){
                        opt.onUnfoldEnd.call($this, $content);
                    }
                    if (flag == '1'){
                        opt.onFoldEnd.call($this, $content);
                    }
                }
            });
        }
    }

    $.fn.sanExpander = function(){
        var expander = san.tools.objectCreate(san.widget);
        return expander.init(this, methods, arguments);
    };
})(jQuery);



function recordsSplit(records, min, max){
    var rec = [];
    if (min < 0) {min = 0;}
    if (max < min) {max = min + 1;}

    $.each(records, function(n, v){
        if (n >= min && n < max) {
            rec.push(v);
        }
    });
    return rec;
}



function setDownloadIcon (mark) {
    var suffix = '';
    switch (('' + mark).toLowerCase()) {
        case 'pdf':
            suffix = MURL + 'images/icon-pdf-170515.png';
            break;
        case 'doc':
        case 'docx':
        case 'word':
            suffix = MURL + 'images/icon-word-170515.png';
            break;
        case 'xls':
        case 'xlsx':
        case 'excel':
            suffix = MURL + 'images/icon-excel-170515.png';
            break;
        case 'other':
        case 'others':
        case 'rar':
        case 'zip':
            suffix = MURL + 'images/icon-other-170515.png';
        // no default;
    }
    return suffix;
}



;(function($){
    'use strict';

    var config = {
        // CLASS，容器
        container: 'section-slide',
        // CLASS，滑动容器
        list: 'section-slide-list',
        handle: ['section-slide-handle-prev', 'section-slide-handle-next'],
        activeHandle: ['section-slide-handle-active-prev', 'section-slide-handle-active-next'],
        // CLASS，当前显示项
        current: 'current',
        // 列数
        col: 1,
        // 持续时间
        duration: 200,
        onInit: function(){},
        // 点击后执行，需要return true或false。返回true时执行后续代码，返回false中止执行。
        // $btn: 点击的按钮
        onClick: function($btn){},
        // 点击后执行，在动画完成后执行
        onNext: function(){},
        onPrev: function(){},
        // 当前项是第一项时执行，最后执行
        onFirst: function(){},
        // 当前项是最后一项时执行，最后执行
        onLast:function(){}
    }

    var namespace = 'sanSlideSection';

    var methods = {
        init: function(option){
            return this.each(function(){
                var $this = $(this),
                    opt = $.extend({}, config, option),
                    $list = null, $next = null, $prev = null,
                    $current = null,
                    cw, n, w, t, i = 0, left = 0, 
                    flag = true;
                
                $this.data('options', opt);
                $list = $this.find('.' + opt.list);
                $next = $this.find('.' + opt.handle[1]);
                $prev = $this.find('.' + opt.handle[0]);
                n = $list.find('li').length;
                t = n / opt.col - 1;
                if (n > 1){
                    $next.addClass(opt.activeHandle[1]);
                }

                $list.children('li').each(function(i){
                    var $li = $(this);
                    if (i == 0) {
                        $current = $li;
                    }
                    $li.attr('data-index', i);
                });
                
                $current.addClass(opt.current);
                
                methods.setup.call($this, 0);
    
                opt.onInit.call($this);
                
                $this.off('click.' + namespace, '.' + opt.activeHandle[1]);
                $this.on('click.' + namespace, '.' + opt.activeHandle[1], function(){
                    var onClick = opt.onClick.call($this, $(this));
                    if (onClick !== undefined) flag = onClick;
                    if (!flag) return;
                    i++;
                    if (i > t){
                        i = t;
                        return;
                    }else{
                        if (i == t) $next.removeClass(opt.activeHandle[1]);
                        $prev.addClass(opt.activeHandle[0]);
                    }

                    methods.setCurrent.call($this, i, opt.onNext);
                });
    
                $this.off('click.' + namespace, '.' + opt.activeHandle[0]);
                $this.on('click.' + namespace, '.' + opt.activeHandle[0], function(){
                    var onClick = opt.onClick.call($this, $(this));
                    if (onClick !== undefined) flag = onClick;
                    if (!flag) return;
                    i--;
                    if (i < 0){
                        i = 0;
                        return;
                    }else{
                        if (i == 0) $prev.removeClass(opt.activeHandle[0]);
                        $next.addClass(opt.activeHandle[1]);
                    }

                    methods.setCurrent.call($this, i, opt.onPrev);
                });

                var inTimer = null;
                $(window).on('resize.' + namespace, san.tools.throttle(function(){
                    clearInterval(inTimer);
                    inTimer = setInterval(function(){
                        if (GLOBE_INIT) {
                            clearInterval(inTimer);
                            methods.setup.call($this, parseInt($list.children('li.current').attr('data-index')));
                        }
                    }, 10);
                }, 200));
            });
        },
        setup: function(index){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $list = null,
                    n, w;
                $list = $this.find('.' + opt.list);
                n = $list.children('li').length;
                w = $this.width();
                $list.find('li').css('width', w + 'px');
                $list.css({
                    'width': w * n + 'px',
                    'height': $list.children('li.current').height() + 'px',
                    'margin-left': '-' + index * w * opt.col + 'px'
                });
            });
        },
        setCurrent: function(index, callback){
            return this.each(function(){
                var $this = $(this),
                    opt = $this.data('options'),
                    $list = null, $current = null,
                    length,
                    left;

                $list = $this.find('.' + opt.list);
                $current = $list.children('li:eq(' + index + ')');
                $current.addClass(opt.current).siblings().removeClass(opt.current);
                $list.css('height', $current.height() + 'px');
                length = $list.find('li').length;

                left = $this.width() * opt.col * index;

                $list.stop(true, true).animate({'margin-left': '-' + left + 'px'}, opt.duration, function(){
                    if (san.tools.type(callback) == 'function') {
                        callback.call($this);
                    }
                    if (index == 0) { opt.onFirst.call($this); }
                    if (index == (length - 1)) { opt.onLast.call($this); }
                });
            });
        }
    }

    $.fn.sanSlideSection = function(){
        var expander = san.tools.objectCreate(san.widget);
        return expander.init(this, methods, arguments);
    };
})(jQuery);




/* 
 * 下拉多选选择器
 * 参数：
 * $input: 输入域对象
 * checkSelector：获取同组选择按钮的CSS选择器
 * 多选规则：
 * 1. 多选按钮选择值都会赋给输入域的value和data-value中；
 * 2. 输入域的value用于显示，所以存放的是选中项的文本值。即label的文本内容；
 * 3. 输入域的data-value用于存放选中项的value值，即checkbox的value值；
 * 4. 默认选中“全选”按钮；
 * 5. 输入域不支持空值，当没有任何选择按钮被选中时，将自动选中“全部”按钮；
 * 6. “全选”规则：当全选时，输入域value获取的是全选按钮的label的文本内容（与其它选择按钮相同），但输入域的data-value获取的是其它选择项的value值集合（以逗号拼接）。（注意，不是全选按钮的value值！）
 */
function droplistMultiSelect($input, checkSelector) {
    var $checkAll = $(checkSelector + '[data-rel="checkall"]');

    $(checkSelector).off('change').on('change', function(){
        var $checkbox = $(this), 
            // 存放多选按钮value值
            results = [],
            // 存放label标签文本
            text = [];
        if ($checkbox.attr('data-rel') == 'checkall' && $checkbox.prop('checked')) {
            // 全选选中
            var $siblings = $checkbox.parent().siblings().find(':checkbox');
            $siblings.prop('checked', false);
            results.push(getAllValue($siblings));
            text.push($checkbox.next().text());
        } else {
            // 非全选
            $checkAll.prop('checked', false);

            $(checkSelector + ':checked').each(function(i){
                var $checked = $(this);
                results.push($checked.val());
                text.push($checked.next().text());
            });
        }

        // 没有选中项，选中全选
        if (results.length == 0) {
            $checkAll.prop('checked', true);
            results = getAllValue($checkAll.parent().siblings().find(':checkbox'));
            text.push($checkAll.next().text());
        }

        $input.val(text.join(','));
        $input.attr('data-value', results.join(','));
    });

    $checkAll.trigger('click');

    function getAllValue($checks) {
        var val = [];
        $checks.each(function(){
            var $this = $(this);
            val.push($this.val());
        });
        return val;
    }
}



/* 
 * 弹窗式备注信息声明
 * 参数：
 * $tips: 弹窗式备注控制柄
 * notesId：备注元素id
 * url：备注远程数据源链接。无此参数备注数据从notedId对象获取
 * 依赖sanTooltips组件
 */
function notesSetup(tips, notesId, url, option) {
    var $notes = $('#' + notesId),
        $tips = (tips instanceof jQuery) ? tips : $(tips),
        attrRole = 'data-role',
        content = null;

    if (!url) {
        content = $notes.html();
        if (san.tools.trim(content) == '') {
            $tips.removeAttr('data-role');
        } else {
            $tips.attr(attrRole, 'notes');
            tooltipsInit();
        }
        return;
    }

    san.tools.getJsonData({
        url: url,
        onDone: function(data){
            content = data.data.rmkCn;
            if (san.tools.trim(content) == '') {
                $tips.removeAttr(attrRole);
                return;
            }
            $notes.html(content);
            $tips.attr(attrRole, 'notes');
            tooltipsInit();
        },
        onFail: function(){
            $tips.removeAttr(attrRole);
        }
    });

    function tooltipsInit() {
        var opt = {
            type: 'html',
            selector: '#' + notesId
        }
        if (san.tools.type(option) == 'object') {
            opt = $.extend(opt, option)
        }
        $tips.sanTooltips(opt);
    }
}



/* 
 * 弹出确认层
 */
function popupConfirm(url, option){
    var opt = {
        type: 'GET',
        cache: false,
        timestamp: true,
        data: null
    }
    var $wrapper = null,
        $popup = null,
        popupId = san.tools.uuid('san-popup-'),
        width = 640,
        strMask = '<div class="san-popup-wrapper"></div>',
        strPop = '<div class="san-popup"></div>';

    opt = $.extend({}, opt, option)
    
    $('body').append('<div class="san-popup-wrapper"><div class="san-popup"></div></div>');
    $wrapper = $('body').children('.san-popup-wrapper');
    $popup = $wrapper.find('.san-popup');
    $popup.attr('data-widget', popupId);

    $popup.sanJumpto({
        url: url,
        type: opt.loadMethod,
        cache: opt.cache,
        timestamp:  opt.timestamp,
        inject: opt.inject,
        injectObj: opt.injectObj,
        onDone: function(data){
            $('body').addClass('san-popup-open');
            popShow(width);
        },
        onFail: function(){
            // ...
        }
    });
    
    san.listener.duplicated($popup[0], RESIZE_LISTENER_GROUP);
    RESIZE_LISTENER_GROUP[popupId] = $popup[0];

    var waitingTimer;
    $popup.on(RESIZE_LISTENER + '.sanPopup', function() {
        clearInterval(waitingTimer);
        waitingTimer = setInterval(function(){
            if (GLOBE_INIT) {
                clearInterval(waitingTimer);
                popupResize(width);
            }
        }, 10);
    });

    function popShow(width) {
        $popup.addClass('san-popup-active');
        popupResize(width);
        $popup.addClass('san-popup-pop-in'); 
    }

    function popupResize(width) {
        var $mainpage = $(TOP_DIV),
            popupWidth, popupHeight, rh = 0;
        popupWidth = Math.max(300, Math.min(width, 1000, V_VW * 0.85));
        popupHeight = $popup.outerHeight();
        rh = V_VH - popupHeight;
        $popup.css({
            'width': popupWidth + 'px',
            'left': (V_VW - popupWidth) * 0.5 + 'px',
            'top': rh > 0 ? rh * 0.5 : 10,
            'overflow-y':'auto'
        });
        
        if (V_VW < MEDIA_RULE.M) {
            $mainpage.css('top', '-' + san.view.scroll().top + 'px').addClass('masked');
        } else {
            if ($mainpage.hasClass('masked')) {
                var top = Math.abs(parseInt($mainpage.css('top')));
                $mainpage.css('top', '').removeClass('masked');
                $('html, body').scrollTop(top);
            }
        }
    }
}

/* 
 * 关闭弹出确认层
 */
function popupConfirmClose(){
    var $mainpage = $(TOP_DIV),
        $wrapper = $('body').children('.san-popup-wrapper'),
        $popup = $wrapper.children('.san-popup');
    
    $popup.removeClass('san-popup-pop-in').addClass('san-popup-pop-out'); 
    
    delete RESIZE_LISTENER_GROUP[$popup.attr('data-widget')];

    setTimeout(function(){
        $popup.removeClass('san-popup-active');
        $wrapper.remove();
        $('body').removeClass('san-popup-open');
        if (V_VW < MEDIA_RULE.M) {
            var top = Math.abs(parseInt($mainpage.css('top')));
            $mainpage.css('top', '').removeClass('masked');
            $('html, body').scrollTop(top);
        }
    }, 200);
}


/** 
 * 文章正文字体大小控制
 * id：控制器id
 * target：正文容器id
 */
var rFontSize = /font-size\s*:\s*(\d*\.?\d*)[A-z|%]*[;"\s]?/gi;
function fontControl(id, target){
    var obj = document.getElementById(target),
        content = $(obj).html(),
        size,
        hasSize = rFontSize.test(content);
    $('#' + id).on('click.font-control', 'a', function(){
        $(this).addClass('active').siblings().removeClass('active');
        size = $(this)[0].getAttribute('data-font');
        obj.style.cssText = 'font-size:' + size + '% !important';
    });
    $('#' + id).find('.active').trigger('click.font-control');
}

/** 
 * 解析URL获取指定的参数
 * URL: test.html?user=abc&password=123&sysno=001
 * 获取：
 * queryUrl("user");
 * queryUrl("password");
 * queryUrl("sysno");  
 */
 function getQueryStr(str){  
    var LocString = String(window.document.location.href);   
    // var rs = new RegExp("(^|)"+str+"=([^/&]*)(/&|$)","gi").exec(LocString),
    var rs = new RegExp("(^|)"+str+"=([^/&]*)(&|$)","gi").exec(LocString),
    //var rs = new RegExp('(\\?|&)'+str+'=([^/&]*)(&|$)','gi').exec(LocString),
        tmp;
    if (tmp = rs) return tmp[2];
    // parameter cannot be found   
    return '';
}

function queryUrl(str){
    var url = decodeURI(window.location.href);
    var rs = new RegExp("(^|)" + str + "=([^/&]*)(&|$)","gi").exec(url);
    if (rs) {return rs[2];}
    return '';
}

//为URL添加时间戳
function convertURL(url){  
    var timstamp = (new Date()).valueOf();  
    if (url.indexOf('?') >= 0){
        url = url + '&t=' + timstamp;   
    }else{  
        url = url + '?t=' + timstamp;  
    };  
    return url;  
}; 

/**
 * @autor wf
 * @date 2017年08月28日 
 */
/*截取指定长度字符并在结尾加上相应的符号
 * str    字符串
 * len    指定长度
 * sublen 截取长度
 * txt    指定符号
 * */
function subStrCom(str,len,sublen,txt){
	var strlen = 0;	
	var substr="";//返回的截取字符
	var sublenStr = "";//截取长度时的字符串	
	for(var i=0;i<str.length;i++){
		var code = str.charCodeAt(i);
		var char = str.charAt(i);
		if(code>128){
			strlen += 2;
		}else{
			strlen += 1;
		}
		if(strlen <= sublen){//当strlen<=sublen,获取字符串
			sublenStr += char;
		}
	}
	if(strlen > len){
		substr = sublenStr + txt;
	}else{
		substr = str;
	}
	return substr;
}
/*截取指定长度字符并在结尾加上"..."代替超出的长度字符串
 * str    字符串
 * len    指定长度
 * sublen 截取长度
 * */
function subStrDot(str,len,sublen){
	var strlen = 0;	
	var substr="";//返回的截取字符
	var sublenStr = "";//截取长度时的字符串	
	for(var i=0;i<str.length;i++){
		var code = str.charCodeAt(i);
		var char = str.charAt(i);
		if(code>128){
			strlen += 2;
		}else{
			strlen += 1;
		}
		if(strlen <= sublen){//当strlen<=sublen,获取字符串
			sublenStr += char;
		}
	}
	if(strlen > len){
		substr = sublenStr + "...";
	}else{
		substr = str;
	}
	return substr;
}


/**
 * 将字符串中的特殊字符转为实体编码或实体字符
 * @author: zhxming
 */
function sanCharEntity(str){
    var reg = /['"&\\/<>]/g;
    return str.replace(reg, function(match){
        switch (match){
            case '"':
                return '&#34;';
            case '&':
                return '&#38;';
            case '\'':
                return '&#39;';
            case '\\':
                return '&#92;';
            case '<':
                return '&#60;';
            case '>':
                return '&#62;';
            case '/':
                return '&#47;';
        }
    });
}

function getContentPathById(json,id,size){
	var href;
	var arr = new Array();
	for(var i=0;i<size;i++){
		arr = json[i];
		var contentId = arr.contentId;
		if(contentId===id){
			break; 
		}
	}
	href = arr.draftPath;
	
	return href;
}

/**
 * 稿件展示的正文、附件信息
 * 3.122.0-中文版SEO
 * zengtao
 * 20190429
 * */
function contentShowInfoSEO(contentId, txt, attSize, doc, draftPath){
	var arrObj = new Array();
	var suffix="",href="",downloadHref="",docType = "";
	if(null!=doc){
		docType = doc.toLowerCase();
	}
	if(attSize==1&&txt==0){//正文不存在并且只有一个附件，显示小图标
		if (typeof(isGray) != "undefined" && isGray) {
			if(docType=="pdf"){					
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-pdf-170515.png" />';
			}else if(docType=="doc"||docType=="docx"){ 
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-word-170515.png" />';						
			}else if(docType=="xls"||docType=="xlsx"){
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-excel-170515.png" />';
			}else{
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-other-170515.png" />';
			}
			downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			
		} else {
			if(docType=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-pdf-170515.png" />';
			}else if(docType=="doc"||docType=="docx"){
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-word-170515.png" />';						
			}else if(docType=="xls"||docType=="xlsx"){
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-excel-170515.png" />';
			}else{
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-other-170515.png" />';
			}
			downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			
		}
		
	}else{//正文存在且只有一个附件，或有多个附件，不显示图标，点击链接打开内容
		suffix = "";
		downloadHref = "javascript:;";
	}
	href = draftPath;
	arrObj.push(suffix);
	arrObj.push(href);
	arrObj.push(downloadHref);
	
	return arrObj;
}

/*
 * channelPath channel id 所对应的path
 */
function getChannelId(channelPath){
	var id = "";
	var channelArray = channelPath.split(",");
	$.ajax({
		url:"/chinese/cxsymb/index.html",
		type:"POST",
		dataType : 'text',
		cache : false,	
		async:false,
		success:function(data){
			var str = data.substring(0,data.lastIndexOf(","))+"]";			
			var jsonArr = JSON.parse(str);
			for (var i = 0; i < channelArray.length; i++) {
				var channelObj = jsonArr.filter(function(p){				
					return p.path == channelArray[i];
				});				
				id += channelObj[0].id;
				if(i != (channelArray.length - 1)){
					id += ",";
				}
			}
		}
	});
	return id;
}

/*
 *解决filter方法在IE8及其以下版本兼容问题
 * @author wufeng
 * 2017-11-24
 * eg:getChannelId方法中的filter方法
 * */
//$(function(){
	if(!Array.prototype.filter){
	    Array.prototype.filter = function(fun){
	        if(this === void 0 || this === null){
	        	throw new TypeError();
	        }
	        var t = Object(this);
	        var len = t.length>>>0;
	        if(typeof fun !=='function'){
	        	throw new TypeError();
	        }
	        var res = [];
	        var thisArg = arguments.length>=2 ? arguments[1]:void 0;
	        for(var i=0;i<len;i++){
	            if(i in t){
	                var val = t[i];
	                if(fun.call(thisArg,val,i,t)){res.push(val);}
	            }
	        }
	        return res;
	    };
	}
//});


/**
 * 稿件展示的正文、附件信息
 * */
function contentShowInfo(contentId, txt, attSize, doc, draftPath){
	var arrObj = new Array();
	var suffix="";
	var href="";
	var downloadHref="";
	var docType = "";
	if(null!=doc){
		docType = doc.toLowerCase();
	}
	if(attSize==1&&txt==0){//正文不存在并且只有一个附件，显示小图标
		if (typeof(isGray) != "undefined" && isGray) {
			if(docType=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-pdf-170515.png" />';
				href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=open';
				downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			}else{
				if(docType=="doc"||docType=="docx"){//doc格式文件 
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-word-170515.png" />';						
				}else if(docType=="xls"||docType=="xlsx"){//xls格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-excel-170515.png" />';
				}else{//其他格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-other-170515.png" />';
				}
				//href = getContentPath(contentId);
				href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
				downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			}
		} else {
			if(docType=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-pdf-170515.png" />';
				href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=open';
				downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			}else{
				if(docType=="doc"||docType=="docx"){//doc格式文件 
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-word-170515.png" />';						
				}else if(docType=="xls"||docType=="xlsx"){//xls格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-excel-170515.png" />';
				}else{//其他格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-other-170515.png" />';
				}
				//href = getContentPath(contentId);
				href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
				downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			}
		}
		
	}else{//正文存在且只有一个附件，或有多个附件，不显示图标，点击链接打开内容
		suffix = "";
		href = draftPath;
		downloadHref = "javascript:;";
	}
	arrObj.push(suffix);
	arrObj.push(href);
	arrObj.push(downloadHref);
	
	return arrObj;
}

/*
 * 分页
 * id   元素id
 * rdTotal 分页数据总数量
 * pgTotal 分页数据总页数
 * pageNum 当前页
 */
function pagination(id,pgTotal,rdTotal,pgNum){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}

        	renderData(num);
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){        		
        		renderData(prevNum);
        	}else{
        		renderData(num);	
        	}        	
        }
    });
}

/*
 * 分页
 * id   元素id
 * rdTotal 分页数据总数量
 * pgTotal 分页数据总页数
 * pageNum 当前页
 */
function pagination7(id,pgTotal,rdTotal,pgNum,topId){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
       	backToTop:true,
       	backToTopId:topId,
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}

        	renderData(num);
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){        		
        		renderData(prevNum);
        	}else{
        		renderData(num);	
        	}        	
        }
    });
}

/*
 * 分页
 * id   元素id
 * rdTotal 分页数据总数量
 * pgTotal 分页数据总页数
 * pageNum 当前页
 */
function pagination4(id,pgTotal,rdTotal,pgNum){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}
        	renderData_one(num);
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){        		
        		renderData_one(prevNum);
        	}else{
        		renderData_one(num);	
        	}        	
        }
    });
}

/*
 * 分页
 * id   元素id
 * rdTotal 分页数据总数量
 * pgTotal 分页数据总页数
 * pageNum 当前页
 */
function pagination5(id,pgTotal,rdTotal,pgNum,topId){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
       	backToTop:true,
       	backToTopId:topId,
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}
        	renderData_one(num);
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){        		
        		renderData_one(prevNum);
        	}else{
        		renderData_one(num);	
        	}        	
        }
    });
}

/*
 * 分页
 * id   元素id
 * rdTotal 分页数据总数量
 * pgTotal 分页数据总页数
 * pageNum 当前页
 */
function pagination3(id,pgTotal,rdTotal,pgNum){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}
        	renderData_new(num);
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){        		
        		renderData_new(prevNum);
        	}else{
        		renderData_new(num);	
        	}        	
        }
    });
}

/*
 * 分页
 * id   元素id
 * rdTotal 分页数据总数量
 * pgTotal 分页数据总页数
 * pageNum 当前页
 */
function pagination6(id,pgTotal,rdTotal,pgNum,topId){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
       	backToTop:true,
       	backToTopId:topId,
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}
        	renderData_new(num);
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){        		
        		renderData_new(prevNum);
        	}else{
        		renderData_new(num);	
        	}        	
        }
    });
}

/*
 * 获取链接指定name后面的参数
 * eg:http://localhost:8080/fe/Channel/9880861?newChannel=1733
 * 调用getFramesSrc("newChannel") 返回1733
 * */
function getFramesSrc(name){
	var reg = new RegExp("(^|&)"+name+"=([^&]*)(&|$)");
	var channel = window.location.search.substr(1).match(reg);
	if(channel !=null){
		return channel[2];
	}else{
		return null;
	}	
}

/*
 * 大额同业下载功能
 */
function cnDepositExportExcel(enty,bondCode,beginDate,endDate,bondPeriod,couponType,downFlag){
	//sql优化标志位(sqlFlag),1:老逻辑,2:新逻辑
	var href = fileDownUrl+'cnDepositExcelFileDownLoad.do?enty='+enty+'&bondCode='+bondCode+'&beginDate='+beginDate+'&endDate='+endDate+'&bondPeriod='+bondPeriod+
	'&couponType='+couponType+'&downFlag='+downFlag+'&sqlFlag=2';
	return href;
}

function pagination2(id,pgTotal,rdTotal,pgNum, fn){
	$('#'+id).sanPagination({
        setup: {
            pageTotal: pgTotal>0?pgTotal:1,//总页码
            recordsTotal: rdTotal,//总记录数
            pageNum: pgNum//当前页
        },
        onClick: function($li, prevNum){  	
        	var txt = $li.text();
        	var num = 1;
        	if(txt=="下一页"){
        		num = prevNum + 1;
        	}else if(txt=="上一页"){
        		num = prevNum - 1;
        	}else if(txt=="第一页"){
        		num = 1;
        	}else if(txt=="最后页"){
        		num = pgTotal;
        	}
        	if (typeof fn == 'function'){
        		fn(num);
        	}
        },
        onEnter: function($input, prevNum){
        	//直接跳转
        	var num = $input.val();        	
        	if(num==null||num==""){ 
        		if (typeof fn == 'function'){
        			fn(prevNum);
        		}
        	}else{
        		if (typeof fn == 'function'){
        			fn(num);
        		}
        	}        	
        }
    });
}

/**
 * 数字补零
 * @author: zhxming
 * 执行原则：补零后，数值不变。值将被转为String后返回。
 * 参数：
 * n - 要补零的数字
 * digit - number。最大补零位数。默认：2
 * pos - number。补零位置。 值：1（默认）||-1。在左侧或右侧（小数位）补零。
 */
function sanZeroFill(n, digit, pos){
    n = parseFloat(n);
    if (digit === 0 || digit === null || n == 0) { return n + ''; }
    var a = (n + '').split('.');
    if (!a[1]) {a.push('0');}
    digit = (typeof digit === 'number' && digit > 0) ? parseInt(digit, 10) : 2;
    pos = (typeof pos === 'number' && pos < 0) ? -1 : 1;
    
    var i, len = (pos == 1) ? a[0].length : (a[1].length - 1), z = '';
    if (len >= digit) { return n + ''; }
    for (i = 0; i < (digit - len); i++){
        z += '0';
    }

    if (pos == 1){
        return z + n;
    }

    if (pos == -1){
        a[1] = (a[1] + z).substring(0, digit);
        return a[0] + '.' + a[1];
    }
}




//去掉首位空格
function trimStr(str){
	return str.replace(/(^\s*)|(\s*$)/g, "");
}

var DOTABS = false;
function  doJumptoByDatafor(){
	$('body').find('[data-for="block"]').each(function(){
		var role = $(this).attr('data-role');
		if (role === STANDBY_ELEMENT) {
			$(this).sanJumpto({
				type:'GET',
				timestamp:false,
			 	onBefore: function(){
	        $(this).attr('data-status', 'start');
	      },
	      onDone: function() {
	          $(this).attr('data-status', 'done');
	          // 确定页头就绪，其宽度不在改变时，设为true
	          READY_GO = true;
	      },
	      onFail: function() {
	          $(this).attr('data-status', 'failed');
	      }
			});
    }
	});
	var inTimer = setInterval(function(){
      if (GLOBE_INIT) {
        clearInterval(inTimer);
      	$('body').find('[data-for="block"]').each(function(){
					var role = $(this).attr('data-role');
					if (role != STANDBY_ELEMENT) {
						$(this).sanJumpto({
							type:'GET',
							timestamp:false,
						 	onBefore: function(){
				        $(this).attr('data-status', 'start');
				      },
				      onDone: function() {
				          $(this).attr('data-status', 'done');
				      },
				      onFail: function() {
				          $(this).attr('data-status', 'failed');
				      }
						});
			    }
				});
        $('#main-side-menu').sanSideMenu().sanSideMenu('setCurrent', $('#rel-channel-path-id').val());
        DOTABS = true;
      }
  }, 10);
}

//获取多条稿件的相关信息
function draftInfo(d){
	var contentIds="";
	var size = d.length;
	$.each(d,function(i,n){
		var contentId = n.contentId;
		if(i != (size-1)){
			contentIds += contentId+",";
		}else{
			contentIds += contentId;
		}
	});	
	var jsonStr="";
	$.ajax({
		url:NT_URL+"/cm-s-notice-query/draftInfo",
        data:{"contentIds":contentIds},
		type:"POST",
		dataType : 'json',
		cache : false,
		async:false,
		success:function(data){
			var size = 0;
			if(data.data!=null){
				size = data.data.size;
			}			
			var suffix = "";
			var downloadHref = "";
			var href = "";
			
			$.each(data.records,function(i,n){
				
				var contentId = n.contentId;
				//是否存在正文
				var txt = n.txt;
				//附件个数
				var attSize = n.attachmentSize;
				//附件后缀名
				var docType = n.suffix;
				var fileFormat = "";
		        if(null!=docType) {
		        	fileFormat = docType.toLowerCase();
		        }
				//正文路径
				var draftPath = n.draftPath;
				if(attSize==1&&txt==0){//正文不存在并且只有一个附件，显示小图标,点击链接和图标都下载附件
					if(fileFormat=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
						suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-pdf-170515.png' />";
						href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=open';
						downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
					}else{
						if(fileFormat=="doc"||fileFormat=="docx"){//doc格式文件  显示小图标,点击链接和图标都下载附件
							suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-word-170515.png' />";						
						}else if(fileFormat=="xls"||fileFormat=="xlsx"){//xls格式文件 显示小图标,点击链接和图标都下载附件
							suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-excel-170515.png' />";
						}else{//其他格式文件 显示小图标,点击链接和图标都下载附件
							suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-other-170515.png' />";
						}
						href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
						downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
					}
				}else{
					suffix = "";
					href = draftPath;
					downloadHref = "javascript:;";
				}				
				
				if(i != (size-1)){
					jsonStr += '{"contentId":"'+contentId+'","suffix":"'+suffix+'","href":"'+href+'","dhref":"'+downloadHref+'"},';
				}else{
					jsonStr += '{"contentId":"'+contentId+'","suffix":"'+suffix+'","href":"'+href+'","dhref":"'+downloadHref+'"}';
				}
				
			});
		}
	});
	var jsonStr = '['+jsonStr+']';
	var json = JSON.parse(jsonStr);
	return json;
}


function getDraftInfoById(json,id,size){
	var arr;
	var obj = new Array();
	for(var i=0;i<size;i++){
		arr = json[i];
		var contentId = arr.contentId;
		if(contentId===id){
			break; 
		}
	}
	obj.push(arr.suffix);
	obj.push(arr.href);
	obj.push(arr.dhref);
	
	return obj;
}
function getDraftOtherInfos() {
	var suffix = "";
	var downloadHref = "";
	var href = "";
	$.each(data.records,function(i,n){
		var contentId = n.contentId;
		//是否存在正文
		var txt = n.txt;
		//附件个数
		var attSize = n.attachmentSize;
		//附件后缀名
		var docType = n.suffix;
		var fileFormat = "";
        if(null!=docType) {
        	fileFormat = docType.toLowerCase();
        }
		//正文路径
		var draftPath = n.draftPath;
		if(attSize==1&&txt==0){//正文不存在并且只有一个附件，显示小图标,点击链接和图标都下载附件
			if(fileFormat=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
				suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-pdf-170515.png' />";
				href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=open';
				downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			}else{
				if(fileFormat=="doc"||fileFormat=="docx"){//doc格式文件  显示小图标,点击链接和图标都下载附件
					suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-word-170515.png' />";						
				}else if(fileFormat=="xls"||fileFormat=="xlsx"){//xls格式文件 显示小图标,点击链接和图标都下载附件
					suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-excel-170515.png' />";
				}else{//其他格式文件 显示小图标,点击链接和图标都下载附件
					suffix = "<img class='hasGray' src='/r/cms/chinese/chinamoney/assets/images/icon-other-170515.png' />";
				}
				href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
				downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
			}
		}else{
			suffix = "";
			href = draftPath;
			downloadHref = "javascript:;";
		}				
		
		if(i != (size-1)){
			jsonStr += '{"contentId":"'+contentId+'","suffix":"'+suffix+'","href":"'+href+'","dhref":"'+downloadHref+'"},';
		}else{
			jsonStr += '{"contentId":"'+contentId+'","suffix":"'+suffix+'","href":"'+href+'","dhref":"'+downloadHref+'"}';
		}
		
	});
}

//82.0
function getLT(){
	//其中添加获取用户信息lt by jzj 2018-10-25
	var arrObj = new Array();
	var ut;
    var sign;
     $.ajax({
    	 url:LSS_URL+"cm-s-account/getLT",		
			type: "post",
			dataType: 'json',
			cache: false,
			async:false,
			success: function(data) {
                            ut = encodeURI(data.data.UT).replace(/\+/g,'%2B');
                            sign = encodeURI(data.data.sign).replace(/\+/g,'%2B');
            }
     });	
     arrObj.push(ut);
	 arrObj.push(sign);
	 return arrObj;
}



//常见问题折叠效果-fll update， 晓明-edit
function subExpanderBindQuestion(faqId, iframeId){
    $('#'+faqId).find('.san-expander').each(function(){
        var $ex = $(this);
        
        $ex.sanExpander({
            eventBind: false,
            fold: 'san-expander-fold-170724',
            unfold: 'san-expander-unfold-170724',
            autoFold: true
        });

        var exid = $ex.attr('data-exid');
        var $content = $ex.find('.san-expander-content[data-exid=' + exid + ']'),
            $panel = $content.children();

        $ex.on('click.self.sanExpander', '.san-expander-btn[data-exid=' + exid + ']', function(){
            var $block = $panel.children('.section-block');
            var fold = ($content.attr('data-fold') == '1') ? true : false ;
            if (fold){
                var blockLoaded = ($block.attr('data-loaded') == '1') ? true : false;
                if (blockLoaded){
                    $ex.sanExpander('unfold', null, null, null, null, function(){
                        parent.dyniframesize(iframeId);
                    });
                    $ex.siblings('.san-expander').each(function(){
                    	if ($(this).find('[data-fold=0]').length != 0){
	                    	$(this).sanExpander('fold', null, null, null, null, function(){
	                            parent.dyniframesize(iframeId);
	                        });
                    	}
                    });
                }
                if (!blockLoaded){
                    // 加载内容
                    //console.log("url:"+$block.attr('data-url'));
                    $block.sanJumpto1({
                        target: "data-url",
                        inject: true,
                        onDone: function(){
                        	$ex.sanExpander('unfold', false);
                        	
                            $content.attr('data-max', $panel.outerHeight(true));
                            $ex.sanExpander('calculate', null, null, function(){
                                parent.dyniframesize(iframeId);
                            });
                            $block.attr('data-loaded', '1');
                            
                            $ex.siblings('.san-expander').each(function(){
                            	if ($(this).find('[data-fold=0]').length != 0){
        	                    	$(this).sanExpander('fold', null, null, null, null, function(){
        	                            parent.dyniframesize(iframeId);
        	                        });
                            	}
                            });
                            
                            //img
                            $content.find('img').each(function(){
                            	var $img = $(this),
                            	    img = new Image();
                            	img.onload = function(){
                            		$content.attr('data-max', $panel.outerHeight(true));
                            		$ex.sanExpander('calculate', null, null, function(){
                                        parent.dyniframesize(iframeId);
                                    });
                            	}
                            	img.src = $img[0].src;
                            });
                        },
                        onFail: function(){
                            $block.attr('data-loaded', '0');
                        }
                    });
                }
            }else{
                // to fold
                $ex.sanExpander('fold', null, null, null, null, function(){
                    parent.dyniframesize(iframeId);
                });
            }
        });
    });
}

/**
 * 稿件展示的正文、附件信息
 * */
function contentShowInfoNote(contentId, txt, attSize, doc, draftPath){
	var arrObj = new Array();
	var suffix="";
	var href="";
	var downloadHref="";
	var docType = "";
	if(null!=doc){
		docType = doc.toLowerCase();
	}
	if(attSize==1&&txt==0){//正文不存在并且只有一个附件，显示小图标
		if (typeof(isGray) != "undefined" && isGray) {
			if(docType=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-pdf-170515.png" />';
			}else{
				if(docType=="doc"||docType =="docx"){//doc格式文件 
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-word-170515.png" />';						
				}else if(docType=="xls"||docType =="xlsx"){//xls格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-excel-170515.png" />';
				}else{//其他格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/css/gray/img-cm-layout/gray/icon-other-170515.png" />';
				}					
			}
		} else {
			if(docType=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
				suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-pdf-170515.png" />';
			}else{
				if(docType=="doc"||docType =="docx"){//doc格式文件 
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-word-170515.png" />';						
				}else if(docType=="xls"||docType =="xlsx"){//xls格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-excel-170515.png" />';
				}else{//其他格式文件
					suffix = '<img src="/r/cms/chinese/chinamoney/assets/images/icon-other-170515.png" />';
				}					
			}
		}
	}else{//正文存在且只有一个附件，或有多个附件，不显示图标，点击链接打开内容
		suffix = "";
		downloadHref = "javascript:;";
	}
	arrObj.push(suffix);
	arrObj.push(href);
	arrObj.push(downloadHref);
	
	return arrObj;
}


/**
 * 稿件的正文、附件信息
 * */
function contentTxtAttachment(contentId){
	var arrObj = new Array();
	$.ajax({
		url:NT_URL+"/cm-s-notice-query/txtAttachmentInfo",
        data:{"contentId":contentId},
		type:"POST",
		dataType : 'json',
		cache : false,
		async:false,
		success:function(data){
			//是否存在正文 0-不存在 1-存在
			var txt = data.data.isTxt;
			//附件个数
			var attSize = data.data.attSize;
			//后缀名
			var docType = data.data.suffix;//统一转为小写
			var fileFormat = "";
	        if(null!=docType) {
	        	fileFormat = docType.toLowerCase();
	        }
			var suffix="";
			var href="";
			var downloadHref="";
			if(attSize==1&&txt==0){//正文不存在并且只有一个附件，显示小图标
				if(fileFormat=="pdf"){//正文不存在且为pdf文件，显示图标，点击链接打开附件，点击图标下载附件					
					suffix = '<img class="hasGray" src="/r/cms/chinese/chinamoney/assets/images/icon-pdf-170515.png" />';
					href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=open';
					downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
				}else{
					if(fileFormat=="doc"||fileFormat=="docx"){//doc格式文件 
						suffix = '<img class="hasGray" src="/r/cms/chinese/chinamoney/assets/images/icon-word-170515.png" />';						
					}else if(fileFormat=="xls"||fileFormat=="xlsx"){//xls格式文件
						suffix = '<img class="hasGray" src="/r/cms/chinese/chinamoney/assets/images/icon-excel-170515.png" />';
					}else{//其他格式文件
						suffix = '<img class="hasGray" src="/r/cms/chinese/chinamoney/assets/images/icon-other-170515.png" />';
					}
					//href = getContentPath(contentId);
					href = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
					downloadHref = fileDownUrl+'fileDownLoad.do?contentId='+contentId+'&priority=0&mode=save';
				}
			}else{//正文存在且只有一个附件，或有多个附件，不显示图标，点击链接打开内容
				suffix = "";
				href = getContentPath(contentId);
				downloadHref = "javascript:;";
			}
			arrObj.push(suffix);
			arrObj.push(href);
			arrObj.push(downloadHref);
		}
	});
	return arrObj;
}

/**
 * 通过contentId获取稿件所在的栏目path
 * @param contentId
 */
function getChannelPath(contentId){
	var channelPath;
	$.ajax({
		url:NT_URL+"/cm-s-notice-query/contentInfo",
        data:{"ctnId":contentId},
		type:"POST",
		dataType : 'json',
		cache : false,
		async:false,
		success:function(data){
			if(data.records[0]!=null){
				channelPath = data.records[0].channelPath;
			}else{
				channelPath = "";
			}
		}
	});
	return channelPath;
}

/**
 * 走势图，关于数据中的非数字字符返回false
 * zengtao
 * V3.124.0风格优化
 */
function judgeData(num){
    if(num==='null' || num===undefined || num===null || (num+'').trim()==='' || num==='---'){
        return false;
    }
    return true;
}
/**
 * 走势图tooltip悬浮框样式
 * zengtao
 * V3.124.0风格优化
 * param:tooltip数据对象
 * fix：数值精确位
 * width: seriesName要求对齐，指定宽度
 */
function formatTooltip(param,fix,width){
    var div = '';
    var flag = true;
    var len = param.length;
    width = width || 15;
    
    $.each(param,function(n,v){
        if(judgeData(v.value)){
            if(flag){
                div += '<div style="margin-bottom:5px;"><span>'+param[0]['name']+'</span></div>';
                flag = false;
            }
            if(n == len-1){
                div +='<div>';
            }else{
                div +='<div style="margin-bottom:5px;">';
            }
            
            div +='<span style="display:inline-block;margin-right:8px;border-radius:8px;width:8px;height:8px;line-height:8px;background-color:'+v.color+'"></span>';
            if(len>1){
                div +='<span style="display:inline-block;margin-right:8px;width:'+width+'px">'+v.seriesName+'</span><span style="margin-right:3px;">:</span>' 
            }   
            div +='<span>'+((fix==null)? v.value : parseFloat(v.value).toFixed(fix))+'</span></div>'
        }
    })
    return div;
}
/**
 * echarts走势图公用配置项
 * zengtao
 * V3.124.0风格优化
 */
;(function(){
    'use strict';

    var config = {
        color:['#005293','#00b376','#e72742','#773de1','#30a3ff','#d7ac00','#377f97','#9a2b00','#c7a478','#dddbd9'],
        textStyle:{
            color:'#333',
            fontFamily:'Arial,"Microsoft Yahei",sans-serif',
            fontSize:9
        },
        title:{
            text:''
        },
        tooltip:{
            show:true,
            trigger:'axis',
            snap:true,
            axisPointer:{
                type:'line',
                axis:'x',
                lineStyle:{
                    color:'red'
                }
            },
            hideDelay:10,
            confine:true,
            backgroundColor: 'rgba(245, 245, 245, 0.8)',
            borderWidth: 1,
            borderColor: '#ccc',
            padding: 10,
            textStyle: {
                color: '#000',
                fontSize:12,
                lineHeight:10,
                fontFamily:'Arial,"Microsoft Yahei",sans-serif'
            },
            extraCssText:'z-index:1'

        },
        grid:{
            //show:true,//表格封闭线
            containLabel:true,
            top:'5%',
            bottom:'5%',
            left:'7%',
            right:'7%'
        },
        graphic:[
            {
                id:'text',
                type:'text',
                right:'10%',
                bottom:'20%',
                cursor:'defalut',
                style:{
                    text:'chinamoney.com.cn',
                    opacity:0.8
                }
            }
        ],
        xAxis: {
            type: 'category',
            boundaryGap:false,
            name:'',
            nameLocation:'end',
            nameGap:5,
            position:'bottom',
            axisLine:{
                show:false,
                onZero:false,
                lineStyle:{
                    type:'dashed',
                    opacity:0.5
                }
            },
            axisLabel:{
                showMinLabel:true,
                showMaxLabel:true,
                show:true,
                align:'center',
                fontSize:9,
                fontFamily:'Arial,"Microsoft Yahei",sans-serif'
            },
            axisTick:{
                show:false,
                length:3,
                lineStyle:{
                    opacity:0.7
                }
            }
        },
        yAxis: {
            type: 'value',
            boundaryGap:['0%','1%'],
            scale:true,
            name:'',
            nameLocation:'end',
            nameGap:5,
            axisLine:{
                show:false,
                onZero:true
            },
            axisTick:{
                show:false
            },
            splitLine:{
                show:true,
                lineStyle:{
                    color:'#333',
                    type:'dashed',
                    opacity:0.5
                }
            },
            axisLabel:{
                show:true,
                showMinLabel:true,
                showMaxLabel:true,
                inside:true,
                verticalAlign:'bottom',
                fontSize:9,
                fontFamily:'Arial,"Microsoft Yahei",sans-serif'
            },
            splitNumber:3
        }        
    };

    var methods = {
        init: function(option){
            return this.each(function(){
                var $this = $(this),
                    opt  = $.extend(true,{},config,option),
                    id = $this.attr('id');

                $this.data('options', opt);
                
                echarts.dispose(echarts.init(document.getElementById(id)));
                var chart = echarts.init(document.getElementById(id));

                chart.setOption(opt);
                $(window).on('resize.'+id,function(){
                    chart.resize();
                });
            })
        }
    };

$.fn.sanCharts = function(){
    var $charts = san.tools.objectCreate(san.widget);
    return $charts.init(this, methods, arguments);
};
})(jQuery);

/**
 * sanJumpto1
 * 常见问题专用
 * @author: zhxming
 */
;(function($){
    'use strict';

    var config = {
        jumpType: 'ajax',
        //加载文件路径，默认从自定义属性data-url获取
        target: 'data-url',
        //指定加载文件路径，优先于target
        url: '',
        //加载对象不存在时默认指向url
        defaultUrl: 'temp.html',
        // GET || POST
        type: 'POST',
        cache: true,
        // 是否添加时间戳
        timestamp: true,
        async: true,
        //是否允许注入替换
        inject: false,
        //注入替换对象。属性名即页面中要替换的对象，必须以 {{ 和 }} 包裹住，当数据获取成功并且还未加载时，将被替换成对应的属性值
        injectedVar: {},
        //回调，加载开始前执行。
        onBefore: function(){},              
        //回调，加载成功后执行。
        onDone: function(){},
        //回调，加载失败后执行。
        onFail: function(){},  
        //回调，加载时的执行，不论加载成功或失败。
        onAlways: function(){}             
    }

    var methods = {
        init: function(option){
            return this.each(function(){
                var opt = $.extend({}, config, option);
                var $this = $(this);
                opt.type = (opt.type + '').toUpperCase();
                $this.data('opt', opt);

                if (opt.jumpType == 'ajax'){
                    methods.ajax.call($this);
                }
            });
        },
        ajax: function(){
            return this.each(function(){
                var $this = $(this);
                var opt = $this.data('opt');

                var u = opt.url || $this.attr(opt.target) || opt.defaultUrl;
                if (opt.timestamp) {
                    u = convertURL(u);
                }

                $.ajax({
                    url: u,
                    cache: opt.cache,
                    async: opt.async,
                    type: opt.type,
                    beforeSend: function(){
                        opt.onBefore.call($this);
                    }
                }).done(function(data){
                    var html = data;
                    // 过滤掉多余标签，只保留<body>内部分
                    if (eraseHTML(data)) {
                        var str = data.slice(data.indexOf('id="ewebeditor_content"'));
                        var start = str.indexOf('>') + 1,
                            end = str.lastIndexOf('<div id="cjwtdingwei">')-6;
                        html = $.trim(str.slice(start, end));
                    }else{
                    	html="";
                    }
                    //替换注入变量
                    if (opt.inject){
                        html = html.replace(/\{\{[^\}\}]*\}\}/g, function(m){
                            var _m = m.replace(/(\{\{|\}\})/g, '');
                            var s = opt.injectedVar[_m];
                            return (s !== undefined) ? s : m;
                        });
                    }
										
                    $.when($this.html(html).promise()).done(function(){
                    		/*var d = u.split('/')[3];
                    		var t1 = new Date(timeNode).getTime();
							          var t2 = new Date(d.substring(0,4)+"-"+d.substring(4,6)+"-"+d.substring(6,8)).getTime();
							          if(t1>t2){
							          	var arr = new Array();
							          	var arr1 = new Array();
							          	$this.find('*').each(function(n,v){
							          	if($(this).attr('style')){
							          		if($(this).attr('style').toLowerCase().indexOf('font-size')>=0){
															var s = parseFloat($(this).css('font-size').substring(0,$(this).css('font-size').length-2));
															arr[n] = s;
														}
														if($(this).attr('style').toLowerCase().indexOf('font-family')>=0){
															$(this).css('font-family','Arial,"Microsoft Yahei",sans-serif');
														}
														if($(this).attr('style').toLowerCase().indexOf('line-height')>=0){
															var s = parseFloat($(this).css('line-height').substring(0,$(this).css('line-height').length-2));
															arr1[n] = s;
														}
							          	}
													});
													$this.find('*').each(function(n,v){
														if($(this).attr('style')){
															$(this).css('font-size',arr[n]*7/6+"px");
															$(this).css('line-height',arr1[n]*7/6+"px");
														}
													});
							          }*/
                        opt.onDone.call($this);
                    });

                    function eraseHTML(str){
                        var reg = /id="ewebeditor_content"[^>]*>/g;
                        return reg.test(str);
                        // var erase = str.indexOf('</body>');
                        // if (erase == -1) return false;
                        // return true;
                    }

                }).always(function(){
                    opt.onAlways.call($this);
                }).fail(function(){
                    opt.onFail.call($this);
                });
            });
        }
    }

    $.fn.sanJumpto1 = function(){
        var o = arguments[0];
        if (typeof o === 'object' || !o) return methods['init'].apply(this, arguments);
        if (!methods[o]) return;
        return methods[o].apply(this, Array.prototype.slice.call(arguments, 1));
    };
})(jQuery);

// 页面打印
function doPrint(div_id){
    var el = document.getElementById(div_id);
    var iframe = document.createElement("IFRAME");
    var doc = null;
    iframe.setAttribute('style', 'position:absolute;width:0px;height:0px;left:-500px;top:-500px;');
    document.body.appendChild(iframe);
    doc = iframe.contentWindow.document;
    // 引入CSS
    doc.write("<LINK rel=\"stylesheet\" type=\"text/css\" href=\"/r/cms/chinese/chinamoney/assets/css/cm-basic.4.css\">");
    doc.write("<LINK rel=\"stylesheet\" type=\"text/css\" href=\"/r/cms/chinese/chinamoney/assets/css/cm-layout.css\">");
    doc.write(el.innerHTML);
    doc.close();    
    iframe.contentWindow.focus();
    setTimeout(function(){
    	iframe.contentWindow.print();
    	document.body.removeChild(iframe);
    },300);    
}

//清除输入框中的默认值
function resetValue2(id,obj,type){	
	if(type=='clean'){
		var dataVal = $("#"+id).attr("data-val");
		var val = $("#"+id).val();
		
		if(dataVal==val){
			$("#"+id).val("");
		}
		obj.style.color='#000';
	}
	if(type=='init'){
		var dataVal = $("#"+id).attr("data-val");
		var val = $("#"+id).val();
		if(dataVal!= val){
			 $("#rating-bnc-ef").val(val);   
              morePage();	
		}
		if(val=="" && dataVal!=null){
			$("#"+id).val(dataVal);
                obj.style.color='#707070';
		}
         }
}

/*
 * 通过content_id获取相应的稿件链接
 * 
 * */
function getContentPath(contentId){
	var pt;
	$.ajax({
		url:NT_URL+"/cm-s-notice-query/contentInfo",
        data:{"ctnId":contentId},
		type:"POST",
		dataType : 'json',
		cache : false,
		async:false,
		success:function(data){
			if(data.records[0]!=null){
                pt = data.records[0].path;
	        }else{
	            pt="javascript:;";
	        }
		}
	});	
	return pt;
}

function makeFDLT(path){
  //其中添加获取用户信息lt by jzj 2018-10-25
	var ut;
    var sign;
	
     $.ajax({
    	 url:LSS_URL+"cm-s-account/getLT",	
			type: "post",
			dataType: 'json',
			cache: false,
			async:false,
			success: function(data) {
                            ut = encodeURI(data.data.UT).replace(/\+/g,'%2B');
                            sign = encodeURI(data.data.sign).replace(/\+/g,'%2B');
                            path = path+"&ut="+ut+"&sign="+sign;
                            window.location.href=fileDownUrl+path;
            }
     });	
}



/**
* 查询-控制查询、翻页按钮
*/
var queryBtnDisabled=false;
var pageFirstClass='';
var pagePrevClass='';
var pageNextClass='';
var pagelastClass='';
function controlQueryPageBtn(queryBtnId,pageId,disableFlag){	
		queryBtnDisabled=disableFlag;
		pageFirstClass=$(pageId).find('.page-first').attr('class');
		pagePrevClass=$(pageId).find('.page-prev').attr('class');
		pageNextClass=$(pageId).find('.page-next').attr('class');
		pagelastClass=$(pageId).find('.page-last').attr('class');
		$(pageId).find('.page-input').attr("disabled",disableFlag);
		if(disableFlag){
				//$(queryBtnId).addClass('disabled');
				$(pageId).find('.page-first').addClass('disabled');
				$(pageId).find('.page-prev').addClass('disabled');
				$(pageId).find('.page-next').addClass('disabled');
				$(pageId).find('.page-last').addClass('disabled');
		}else{
				//$(queryBtnId).removeClass('disabled');
				$(pageId).find('.page-first').attr('class',pageFirstClass);
				$(pageId).find('.page-prev').attr('class',pagePrevClass);
				$(pageId).find('.page-next').attr('class',pageNextClass);
				$(pageId).find('.page-last').attr('class',pagelastClass);
		}
}

// 兼容IE9下的placeholder
function placeholderSupport(id,color){
	var placeholderSupport = 'placeholder' in document.createElement('input');
	if(!placeholderSupport){   // 判断浏览器是否支持 placeholder
        var _this = $("#"+id);
            var left = _this.css("padding-left");
            _this.parent().append('<span  id="placeholder'+id+'" data-type="placeholder" style="left: ' + left + ';line-height:'+_this.css("line-height")+';position: absolute;top: 0;z-index: 10;color: '+color+';">' + _this.attr("placeholder") + '</span>');
            if(_this.val() != ""){
                $("#placeholder"+id).hide();
            }
            else{
                $("#placeholder"+id).show();
            }
            // 点击表示placeholder的标签相当于触发input
        $("#placeholder"+id).on("click", function(){
        	_this.focus();
        });
        _this.on("input propertychange", function(){
            if(_this.val() != ""){
                $("#placeholder"+id).hide();
            }
            else{
                $("#placeholder"+id).show();
            }
        });
        _this.on("keyup", function(e){
        		if(e.keyCode==8){
							if(_this.val() != ""){
	                $("#placeholder"+id).hide();
	            }
	            else{
	                $("#placeholder"+id).show();
	            }
						}
            
        });
        _this.on("blur", function(){
            if(_this.val() != ""){
                $("#placeholder"+id).hide();
            }
            else{
                $("#placeholder"+id).show();
            }
        });
        
    }
}


/**
 * ie置灰
 * zt V3.124.0
 */
function setImgFontGrayForIE($obj){
    if (IS_GRAY && IS_TRIDENT) {
        $obj.find('a').each(function(){
            //修改！important样式
            $(this)[0].style.removeProperty('color');
            $(this)[0].style.setProperty('color','#333');
        })

        $obj.find('img').addClass('hasGray');
        $obj.find('.hasGray').each(function(){
            grayscale(this);
        })
    }
}


/*
 * 浏览器检测，ie7及以下浏览器时显示提示信息
 * 依赖cookie。点击【不再提示】后，将对应cookie值设为0，在该cookie值生命周期内不再显示提示信息
 * text：显示文本
 * expires：cookie保存时间
 * show：设为true时，不管cookie值是多少均显示提示信息
 */
function browserDetector(text, expires, show){
    var d = document,
        flag = 'querySelector' in d,
        cookie = (show === true) ? '1' : getCookie('browserDetectorTips'),
        dura = parseInt(expires, 10) || 0;

    if (!flag || (IE_V <= 8 && IE_V > 0)) {
        if (cookie == '0') {return false;}
        var str  = '<div class="san-alert" id="broser-detector"><div class="inner">';
            str += '<div class="san-grid">';
            str += '<div class="san-grid-r">';
            str += '<a class="san-btn" data-close="1" href="javascript:void(0);">不再提示</a> <a class="san-btn" data-close="0" href="javascript:void(0);">关闭</a>';
            str += '</div>';
            str += '<div class="san-grid-l"><img style="height:13px;" src="/r/cms/chinese/chinamoney/assets/images/jg1.png"/></div>';
            str += '<div class="san-grid-m">' + text + '</div>';
            str += '</div>';
            str += '</div></div>';
        $('body').prepend(str);
        var $detector = $('#broser-detector');
        $detector.on('click.browserDetector', 'a[data-close]', function(){
            var $this = $(this),
                close = parseInt($this.attr('data-close'), 10);
            $detector.off('click.browserDetector').remove();
            if (close){
                addCookie('browserDetectorTips', '0', dura);
            }
        });
    }else{
        addCookie('browserDetectorTips', '1');
    }
}



/*
 * 添加Cookie
 * name: Cookie属性名
 * value：Cookie属性值
 * expiresHours：cookie保存时间，单位：小时，>0有效，否则不保存Cookie，关闭浏览器时Cookie消失
 */
function addCookie(name, value, expiresHours){
    var cookieString = name + '=' + encodeURIComponent(value);
    if (expiresHours > 0) { 
        var date = new Date(); 
        date.setTime(date.getTime() + expiresHours * 3600 * 1000); 
        cookieString = cookieString + '; expires=' + date.toUTCString()+';path=/'; 
    } 
    document.cookie = cookieString; 
} 

/*
 * 获取指定的Cookie属性的值
 * name：Cookie属性名
 */
function getCookie(name){ 
    var strCookie = document.cookie; 
    var arrCookie = strCookie.split(';'); 
    var i = 0, len = arrCookie.length;
    for (; i < len; i++) { 
        var arr = arrCookie[i].split('='); 
        if(sanTrim(arr[0]) == name) {return decodeURIComponent(arr[1])}; 
    }
    return '';
} 

/*
 * 删除指定的Cookie属性
 * name：Cookie属性名
 */
function deleteCookie(name){ 
    var date = new Date(); 
    date.setTime(date.getTime() - 10000);
    document.cookie = name + '=null; expires=' + date.toUTCString(); 
}

/**
 * 去除字符串前后空格
 **/
function sanTrim(text){
    if (text == null) return '';
    if (String.prototype.trim) return String.prototype.trim.call(text);
    var rtrim = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g;       //trim BOM and nbsp, ie9-
    return (text + '').replace(rtrim, '');
}

function refrashChart(frameID, searchDate, address) {
		if (frameID == "bondsSaleSubsectorTranChart") {
			document.getElementById("bondsSaleSubsectorTranChart").src = address
					+ "/bondsSaleSubsectorTranAction.do?method=showChart&searchDate="
					+ searchDate;
		}
		if (frameID == "creditLendSubsectorTranChart") {
			document.getElementById("creditLendSubsectorTranChart").src = address
					+ "/creditLendSubsectorTranAction.do?method=showChart&searchDate="
					+ searchDate;
		}
		if (frameID == "pledgeRepurchaseSubsectorTranChart") {
			document.getElementById("pledgeRepurchaseSubsectorTranChart").src = address
					+ "/pledgeRepurchaseSubsectorTranAction.do?method=showChart&searchDate="
					+ searchDate;
		}
	}

//获取用户信息lt并跳转到信息产品登录校验入口
function checkLogintoRedirect(){
    var ut;
    var sign;
    $.ajax({
        url:LSS_URL+"cm-s-account/getLT?type=0",		
        type: "post",
        dataType: 'json',
        cache: false,
        async:false,
        success: function(data) {
            ut = encodeURI(data.data.UT).replace(/\+/g,'%2B');
            sign = encodeURI(data.data.sign).replace(/\+/g,'%2B');
            var href = "https://idata.chinamoney.com.cn/dqs/rest/ips-s-account/chkAuth?ut="+ut+"&sign="+sign;
            document.location.href = href;
        }
    });
   
}

function helper(key){
    return key.split('').reverse().join('');
}
