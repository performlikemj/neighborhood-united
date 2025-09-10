// Hood United Admin enhancements
(function(){
  function ready(fn){ if(document.readyState!='loading'){fn()} else {document.addEventListener('DOMContentLoaded', fn)} }

  ready(function(){
    // Utility: icon name mapping and SVGs (defined first so callers can use)
    var iconFor = function(href, text){
      href = href || '';
      text = (text || '').toLowerCase();
      if(href.includes('/meals/order')) return 'orders';
      if(href.includes('/meals/mealplan')) return 'mealplan';
      if(href.includes('/meals/meal/')) return 'meals';
      if(href.includes('/meals/shoppinglist')) return 'cart';
      if(href.includes('/meals/instruction') || text.includes('instruction')) return 'note';
      if(href.includes('/meals/pantry') || text.includes('pantry')) return 'pantry';
      if(href.includes('/meals/ingredient') || text.includes('ingredient')) return 'leaf';
      if(href.includes('/meals/dish') || text.includes('dish')) return 'plate';
      if(href.includes('/chefs/chef')) return 'chef';
      if(href.includes('/chefs/chefrequest') || text.includes('request')) return 'clipboard';
      if(href.includes('/reviews/review')) return 'star';
      if(href.includes('/gamification')) return 'trophy';
      if(href.includes('/custom_auth') || href.includes('/auth/user') || text.includes('user')) return 'user';
      if(href.includes('/meals/systemupdate') || text.includes('system')) return 'megaphone';
      return 'dot';
    };

    function svgFor(name){
      switch(name){
        case 'dashboard':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/></svg>';
        case 'user':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/></svg>';
        case 'meals': // plate
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg>';
        case 'plate':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/></svg>';
        case 'leaf':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12c8-10 18-6 18-6s-4 10-14 10c0 0 0 0 0 0"/><path d="M3 12c0 6 6 6 6 6"/></svg>';
        case 'mealplan': // calendar
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>';
        case 'orders': // bag
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8h12l-1 12H7L6 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>';
        case 'cart': // shopping cart
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="20" r="2"/><circle cx="17" cy="20" r="2"/><path d="M3 4h2l2 12h10l2-8H6"/></svg>';
        case 'note':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h6"/></svg>';
        case 'pantry':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="6" width="16" height="12" rx="2"/><path d="M4 10h16"/></svg>';
        case 'chef': // hat-ish
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 11a4 4 0 1 1 8-2 3 3 0 1 1 2 5H6z"/><rect x="7" y="14" width="10" height="3" rx="1"/></svg>';
        case 'clipboard':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="12" height="16" rx="2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>';
        case 'star':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l3 7h7l-5.5 4 2 7-6.5-4-6.5 4 2-7L2 9h7z"/></svg>';
        case 'trophy':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10v4a5 5 0 0 1-10 0V4z"/><path d="M7 4H4a3 3 0 0 0 3 5"/><path d="M17 4h3a3 3 0 0 1-3 5"/><path d="M8 20h8M10 18h4"/></svg>';
        case 'megaphone':
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10v4l12-3v-4L3 10z"/><path d="M15 7v10"/><circle cx="9" cy="16" r="2"/></svg>';
        case 'dot':
        default:
          return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/></svg>';
      }
    }

    // Sidebar enhancements: add label, dashboard link, collapsible groups
    var nav = document.getElementById('nav-sidebar');
    if(nav){
      // Insert 'Navigation' label after filter
      var filterInput = nav.querySelector('input[type="search"], #nav-filter');
      if(filterInput){
        var label = document.createElement('div');
        label.className = 'hu-nav-label';
        label.textContent = 'Navigation';
        if(filterInput.parentNode){
          filterInput.parentNode.insertBefore(label, filterInput.nextSibling);
        } else {
          nav.insertBefore(label, filterInput.nextSibling);
        }
      }

      // Add Dashboard quick link at top if missing
      if(!nav.querySelector('.hu-nav-dashboard')){
        var dash = document.createElement('a');
        dash.className = 'hu-nav-dashboard';
        dash.href = '/admin/';
        var ico = document.createElement('span');
        ico.className = 'hu-ico';
        ico.innerHTML = svgFor('dashboard');
        dash.appendChild(ico);
        dash.appendChild(document.createTextNode('Dashboard'));
        var refNode = (filterInput && filterInput.parentNode === nav) ? filterInput.nextSibling : (filterInput ? filterInput : nav.firstChild);
        nav.insertBefore(dash, nav.querySelector('.hu-nav-label') ? nav.querySelector('.hu-nav-label').nextSibling : refNode);
      }

      // Collapsible app groups
      var captions = nav.querySelectorAll('.caption, a.section');
      captions.forEach(function(cap){
        var holder = cap.closest('div, table, section');
        if(!holder || holder.classList.contains('hu-collapsible')) return;
        holder.classList.add('hu-collapsible');
        // inject caret
        if(!cap.querySelector('.hu-caret')){
          var caret = document.createElement('span');
          caret.className = 'hu-caret';
          cap.prepend(caret);
        }
        var key = 'hu_nav_collapse_' + (cap.textContent || '').trim().toLowerCase().replace(/\s+/g,'_');
        var collapsed = localStorage.getItem(key) === '1';
        if(collapsed){ holder.classList.add('hu-collapsed'); }
        cap.style.cursor = 'pointer';
        cap.addEventListener('click', function(ev){
          ev.preventDefault();
          holder.classList.toggle('hu-collapsed');
          localStorage.setItem(key, holder.classList.contains('hu-collapsed') ? '1' : '0');
        });
      });

      // Icons for model links
      var iconFor = function(href, text){
        href = href || '';
        text = (text || '').toLowerCase();
        if(href.includes('/admin/') && href.endsWith('/')){
          // normalize
        }
        if(href.includes('/meals/order')) return 'orders';
        if(href.includes('/meals/mealplan')) return 'mealplan';
        if(href.includes('/meals/meal/')) return 'meals';
        if(href.includes('/meals/shoppinglist')) return 'cart';
        if(href.includes('/meals/instruction') || text.includes('instruction')) return 'note';
        if(href.includes('/meals/pantry') || text.includes('pantry')) return 'pantry';
        if(href.includes('/meals/ingredient') || text.includes('ingredient')) return 'leaf';
        if(href.includes('/meals/dish') || text.includes('dish')) return 'plate';
        if(href.includes('/chefs/chef')) return 'chef';
        if(href.includes('/chefs/chefrequest') || text.includes('request')) return 'clipboard';
        if(href.includes('/reviews/review')) return 'star';
        if(href.includes('/gamification')) return 'trophy';
        if(href.includes('/custom_auth') || href.includes('/auth/user') || text.includes('user')) return 'user';
        if(href.includes('/meals/systemupdate') || text.includes('system')) return 'megaphone';
        return 'dot';
      };

      // (svgFor is defined above)

      nav.querySelectorAll('li a:not(.addlink)').forEach(function(a){
        if(a.querySelector('.hu-ico')) return;
        var key = iconFor(a.getAttribute('href') || '', a.textContent || '');
        var span = document.createElement('span');
        span.className = 'hu-ico';
        span.innerHTML = svgFor(key);
        a.prepend(span);
      });
    }

    // Move user tools and theme toggle to top-right
    var navRight = document.querySelector('.hu-nav-right');
    if(navRight){
      var userTools = document.getElementById('user-tools');
      var themeToggle = document.getElementById('theme-toggle') || document.getElementById('toggle-theme') || document.querySelector('button[aria-label*="theme" i], button[title*="theme" i]');
      var wrap = document.createElement('div');
      wrap.className = 'hu-user-tools';
      if(userTools){ wrap.appendChild(userTools); }
      if(themeToggle){
        // Normalize any inline svg width/height that use rem
        try{
          themeToggle.querySelectorAll('svg').forEach(function(svg){
            svg.removeAttribute('width');
            svg.removeAttribute('height');
            svg.style.width = '20px';
            svg.style.height = '20px';
          });
        }catch(e){}
        wrap.appendChild(themeToggle);
      }
      if(wrap.childElementCount){ navRight.appendChild(wrap); }
    }

    // Normalize any <svg width/height="*rem"> to CSS widths to avoid console errors
    try{
      document.querySelectorAll('svg[width$="rem"], svg[height$="rem"]').forEach(function(svg){
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.style.width = svg.style.width || '20px';
        svg.style.height = svg.style.height || '20px';
      });
    }catch(_e){}

    // Global search scope routing
    var form = document.getElementById('hu-search');
    if(form){
      form.addEventListener('submit', function(ev){
        var scope = document.getElementById('hu-search-scope').value;
        var q = document.getElementById('hu-search-q').value || '';
        var map = {
          orders: '/admin/meals/order/',
          meals: '/admin/meals/meal/',
          mealplans: '/admin/meals/mealplan/',
          chefs: '/admin/chefs/chef/',
          customers: '/admin/custom_auth/customuser/',
          reviews: '/admin/reviews/review/'
        };
        var base = map[scope] || '/admin/';
        ev.preventDefault();
        window.location.href = base + '?q=' + encodeURIComponent(q);
      });
    }

    // Quick chips from common filters on change list pages
    var cl = document.getElementById('changelist-form');
    var contentMain = document.getElementById('content-main');
    if(cl && contentMain){
      var sub = document.createElement('div');
      sub.className = 'hu-subtabs';
      // Pull some useful filter groups by heading text
      var side = document.getElementById('changelist-filter');
      if(side){
        var groups = side.querySelectorAll('.filter, .choiceform');
        var addGroup = function(title, links){
          if(!links || !links.length) return;
          var group = document.createElement('div');
          group.className = 'hu-chip-group';
          var lab = document.createElement('div'); lab.className='hu-chip-title'; lab.textContent = title; group.appendChild(lab);
          var row = document.createElement('div'); row.className='hu-chip-row';
          links.forEach(function(a){
            var chip = document.createElement('a');
            chip.href = a.href; chip.textContent = a.textContent.trim();
            chip.className = 'hu-chip' + (a.classList.contains('selected') ? ' active' : '');
            row.appendChild(chip);
          });
          group.appendChild(row);
          sub.appendChild(group);
        };

        // Heuristics: find common sections by h3 text
        side.querySelectorAll('.filter').forEach(function(f){
          var h = f.querySelector('h3');
          var links = Array.from(f.querySelectorAll('a'));
          if(!h || !links.length) return;
          var t = h.textContent.toLowerCase();
          if(t.includes('status')) addGroup('Status', links);
          if(t.includes('is paid') || t.includes('paid')) addGroup('Payment', links);
          if(t.includes('delivery')) addGroup('Delivery', links);
          if(t.includes('date')) addGroup('Date', links.slice(0,6));
        });
      }
      if(sub.childElementCount){
        contentMain.insertBefore(sub, contentMain.firstChild);
      }
    }
  });
})();
