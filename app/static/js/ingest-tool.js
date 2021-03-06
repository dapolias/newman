
var validateEmail = function(email) { 
    var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(email);
};
 
var FORM = (function(){
  var items = ['txt_email', 'txt_pass', 'btn-download', 'btn-ingest', 'ingest-options', 'txt_pstemail', 'pst-options', 'btn-pst-extract'];
  var enable = _.partial(_.each, items, function(item){ 
     $('#' + item).removeAttr('disabled');
  });

  var disable = _.partial(_.each, items, function(item){ 
    $("#div-ingest-complete").hide();
    $('#' + item).attr('disabled', 'disabled');
  });

  return {
    enable : enable,
    disable : disable
  };

})();

var logMsgs = function (step, status, msgs){
  $('#div-msg').empty();
  $('#div-msg').append(
    [$('<p>').html("<span class='bold'>Last Refesh:</span> " + (new Date()).toLocaleTimeString()),
     $('<p>').html("<span class='bold'>Process:</span> " + step),
     $('<p>').html("<span class='bold'>Status:</span> " + status)
    ]);
  _.each(msgs, function(msg){ console.log(msg); });
};

var refresh_ingest_options = function(){
  $.ajax({
    'url' : 'ingest/list', 
    'type': 'GET',
    'dataType' : 'json'
  }).then(function(resp){
    $('#ingest-options').empty();    
    
    _.each(resp.items, function(item){
      $('#ingest-options').append($('<option>').html(item));
    });
  });
};

var refresh_pst_options = function(){
  $.ajax({
    'url' : 'pst/list', 
    'type': 'GET',
    'dataType' : 'json'
  }).then(function(resp){
    $('#pst-options').empty();    
    
    _.each(resp.items, function(item){
      $('#pst-options').append($('<option>').html(item));
    });
  });
};

var parseStatus = function(sz){
  var parts = sz.trim().split("\n");
  var statusline = _.last(parts);
  var res = /^\[(.*?)\]/i.exec(statusline)
  return res[1];
};

var pollForStatus = function(url, statuses, callback){
  return function(){
    (function poll(){
      var success = function(resp){
        var status = parseStatus(resp.log);        
        console.log(status);
        var b = _.some(statuses, function(s){
          return s.toLowerCase() == status.toLowerCase();
        });

        logMsgs('Downloading', status, _.last(resp.log.split("\n"), 15));
        //refreshLogItems(_.last(resp.log.split("\n"), 15));

        if (b){
          callback(status)
        } else {
          _.delay(poll, 15 * 1000);
        }
      };

      $.ajax({ url : url, dataType: 'json'}).then(success);
    })();
  };
};

var pollForStatusExtract = function(logname, statuses, callback){
  var url = 'ingest/ingeststate/' + logname;
  var log_url = 'ingest/ingestlog/' + logname;
  return function(){
    (function poll(){
      var success = function(resp){
        var status = parseStatus(resp.log);        
        console.log(status);
        var b = _.some(statuses, function(s){
          return s.toLowerCase() == status.toLowerCase();
        });

        if (b){
          callback(status)
        } else {
          _.delay(poll, 15 * 1000);
        }

        $.ajax({ url : log_url , dataType: 'json'}).then(function(resp){
          logMsgs("Extracting", status, _.last(resp.log.split("\n"), 15));
          //refreshLogItems(_.last(resp.log.split("\n"), 15));
        });
      };

      $.ajax({ url : url, dataType: 'json'}).then(success);
    })();
  };
};


var pollForStatusIngest = function(logname, statuses, callback){
  var url = 'ingest/ingeststate/' + logname;
  var log_url = 'ingest/ingestlog/' + logname;
  return function(){
    (function poll(){
      var success = function(resp){
        var status = parseStatus(resp.log);        
        console.log(status);
        var b = _.some(statuses, function(s){
          return s.toLowerCase() == status.toLowerCase();
        });

        if (b){
          callback(status)
        } else {
          _.delay(poll, 15 * 1000);
        }

        $.ajax({ url : log_url , dataType: 'json'}).then(function(resp){
          logMsgs("Ingesting", status, _.last(resp.log.split("\n"), 15));
          //refreshLogItems(_.last(resp.log.split("\n"), 15));
        });
      };

      $.ajax({ url : url, dataType: 'json'}).then(success);
    })();
  };
};



var ingestComplete = function(){
  $("#div-ingest-complete").show();
};

var run_ingest = function(str){

  FORM.disable();

  var config = $.ajax({
    'url' : 'ingest/config', 
    'type': 'POST',
    'dataType' : 'json',
    'data': JSON.stringify({ 'target' : str, 'filename' : str }),
    'contentType':"application/json; charset=utf-8"    
  });

  var ingest = function(cfg){
    return $.ajax({
      'url' : 'ingest/ingest', 
      'type': 'POST',
      'dataType' : 'json',
      'data': JSON.stringify({ 'conf' : cfg.config }),
      'contentType':"application/json; charset=utf-8"    
    });
  };

  var reload = function(){
    return $.ajax({
      'url' : 'config/reload', 
      'type': 'GET',
      'dataType' : 'json',
      'contentType':"application/json; charset=utf-8"    
    });
  };

  var fail = function(){
    console.log(arguments);
    alert('error');
    FORM.enable();
  };

  config.then(ingest, fail).then(function(resp){
    console.log(resp);
    var logname = resp.log;
    var poll = pollForStatusIngest(logname, ['Complete', 'Error'], function(status){
      FORM.enable();
      reload();
      if (status == 'Complete'){
        $("#div-ingest-complete").show();
      }
      alert(status);
    });
    poll();
    console.log(resp);
  }, fail);

};


var extract_pst = function(email, pst_file) {

  var extract = $.ajax({
    'url' : 'pst/extract', 
    'type': 'POST',
    'dataType' : 'json',
    'data': JSON.stringify({ 'email' : email, 'pst': pst_file }),
    'contentType':"application/json; charset=utf-8"    
  });

  var fail = function(){
    console.log(arguments);
    alert('error');
    FORM.enable();
  };

  FORM.disable();

  extract.then(function(resp){
    console.log(arguments);
    var logname = resp.log;
    var poll = pollForStatusExtract(logname, ['Complete', 'Error'], function(status){
      FORM.enable();
      refresh_ingest_options();
      alert(status);
    });
    poll();
  }, fail);

};

var click_handler_download = function(evt){
  evt.preventDefault();
  var user =  $('#txt_email').val();

  if (!validateEmail(user)){
    alert(user + " is not a valid email address. \nPlease enter a valid email \nexample: sample@gmail.com")
    return;
  };

  var pass =  $('#txt_pass').val();
  var postObj = { 'user' : user, 'pass' : pass };

  FORM.disable();

  var poll = pollForStatus('ingest/state/' + user, ['Completed Download','Error'], function(status){
    FORM.enable();
    refresh_ingest_options();
    alert(status);
  });

  $.ajax({
    url: 'ingest/download',
    type: "POST",
    data: JSON.stringify(postObj),
    contentType:"application/json; charset=utf-8",
    dataType:"json"
  })
    .done(function(resp){
      console.log("success");
      poll();
    })
    .fail(function(resp){
      alert('fail');
      console.log("fail");      
      FORM.enable();
    });

  return false;
};

var click_handler_ingest = function(evt){
  evt.preventDefault();
  var email = $('#ingest-options').val();

  FORM.disable();
  run_ingest(email);

  return false;
};

var click_handler_pst_extract = function(evt){
  evt.preventDefault();

  var email = $('#txt_pstemail').val().trim();

  if (email.length == 0){
    alert('please enter the email associated with this pst');
    return;
  }

  if (!validateEmail(email)){
    alert(email + " is not a valid email address. \nPlease enter a valid email \nexample: sample@gmail.com")
    return;
  };

  extract_pst(email, $('#pst-options').val());
};


$('#btn-download').on('click', click_handler_download);
$('#btn-ingest').on('click', click_handler_ingest);
$('#btn-pst-extract').on('click', click_handler_pst_extract);


//init

refresh_ingest_options();
refresh_pst_options();
