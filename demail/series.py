from elasticsearch import Elasticsearch
from time import gmtime, strftime
import tangelo
from newman.newman_config import default_min_timeline_bound, default_max_timeline_bound
from es_queries import _build_filter


def _date_aggs(date_field="datetime"):
    return {
        "min_date" : { "min" : { "field" : date_field} },
        "max_date" : { "max" : { "field" : date_field } }
    }

def get_datetime_bounds(index, type="emails"):
    es = Elasticsearch()
    resp = es.search(index=index, doc_type=type, body={"aggregations":_date_aggs()})

    now = strftime("%Y-%m-%d", gmtime())
    min = resp["aggregations"]["min_date"].get("value_as_string", default_min_timeline_bound())
    max = resp["aggregations"]["max_date"].get("value_as_string", default_max_timeline_bound())

    return  (min if min >= "1970" else "1970", max if max <= now else now)



def _map_attachments(index, account_id, attchments):
    return {"account_id" : account_id,
            "interval_start_datetime" : attchments[0]["key_as_string"],
            "interval_attach_count" : attchments[0]["doc_count"]
            }

def _map_activity(index, account_id, sent_rcvd):
    return {"account_id" : account_id,
            "interval_start_datetime" : sent_rcvd[0]["key_as_string"],
            "interval_inbound_count" : sent_rcvd[0]["doc_count"],
            "interval_outbound_count" : sent_rcvd[1]["doc_count"]
            }

def entity_histogram_query(email_addrs=[], query_terms='', topic_score=None, date_bounds=None, entity_agg_size=10):
    return {"aggs" : {
        "filtered_entity_agg" : {
            "filter" : _build_filter(email_senders=email_addrs, email_rcvrs=email_addrs, query_terms=query_terms, date_bounds=date_bounds),
            "aggs": {
                "person" : {
                    "terms" : {"field" : "entities.entity_person", "size": entity_agg_size}
                },
                "organization" : {
                    "terms" : {"field" : "entities.entity_organization", "size": entity_agg_size}
                },
                "location" : {
                    "terms" : {"field" : "entities.entity_location", "size": entity_agg_size}
                },
                "misc" : {
                    "terms" : {"field" : "entities.mics", "size": entity_agg_size}
                }

            }
        }}, "size":0}


def get_entity_histogram(index, type, email_addrs=[], query_terms='', topic_score=None, date_bounds=None, entity_agg_size=10):
    tangelo.log("===================================================")
    es = Elasticsearch()
    body = entity_histogram_query(email_addrs=email_addrs, query_terms=query_terms, topic_score=topic_score, date_bounds=date_bounds, entity_agg_size=entity_agg_size)

    tangelo.log("get_entity_histogram: query = %s"%body)

    resp = es.search(index=index, doc_type=type,body=body)
    return sorted([dict(d, **{"type":"location"}) for d in resp["aggregations"]["filtered_entity_agg"]["location"]["buckets"]]
                  + [dict(d, **{"type":"organization"}) for d in resp["aggregations"]["filtered_entity_agg"]["organization"]["buckets"]]
                  + [dict(d, **{"type":"person"}) for d in resp["aggregations"]["filtered_entity_agg"]["person"]["buckets"]]
                  + [dict(d, **{"type":"misc"}) for d in resp["aggregations"]["filtered_entity_agg"]["misc"]["buckets"]], key=lambda d:d["doc_count"], reverse=True)

def attachment_histogram(sender_email_addr, start, end, interval="week"):
    tangelo.log('attachment_histogram(%s, %s, %s, %s)' %(sender_email_addr, start, end, interval))
    return {
        "size":0,
        "aggs":{
            "attachments_filter_agg":{"filter" :
                {"bool":{
                    "must":[{"range" : {"datetime" : { "gte": start, "lte": end }}}]
                }
                },

                "aggs" : {
                    "attachments_over_time" : {
                        "date_histogram" : {
                            "field" : "datetime",
                            "interval" : interval,
                            "format" : "yyyy-MM-dd",
                            "min_doc_count" : 0,
                            "extended_bounds":{
                                "min": start,
                                # "max" doesnt really work unless it's set to "now"
                                "max": end
                            }
                        }
                    }
                }
            }

        }
    }


def attachment_histogram_from_emails(email_addr, date_bounds, interval="week"):
    tangelo.log('attachment_histogram(%s, %s, %s)' %(email_addr, date_bounds, interval))
    return {
        "size":0,
        "aggs":{
            "attachments_filter_agg":{
                "filter" : _build_filter(email_senders=[email_addr], email_rcvr=[email_addr], date_bounds=date_bounds),
                "aggs" : {
                    "attachments_over_time" : {
                        "date_histogram" : {
                            "field" : "datetime",
                            "interval" : interval,
                            "format" : "yyyy-MM-dd",
                            "min_doc_count" : 0,
                            "extended_bounds":{
                                "min": date_bounds[0],
                                # "max" doesnt really work unless it's set to "now"
                                "max": date_bounds[1]
                            }
                        }
                    }
                }
            }

        }
    }


# Returns a sorted map of
def get_daily_activity(index, account_id, type, query_function, **kwargs):
    es = Elasticsearch()
    resp = es.search(index=index, doc_type=type, request_cache="false", body=query_function(**kwargs))
    return [_map_activity(index, account_id, sent_rcvd) for sent_rcvd in zip(resp["aggregations"]["sent_agg"]["sent_emails_over_time"]["buckets"],
                                                                             resp["aggregations"]["rcvr_agg"]["rcvd_emails_over_time"]["buckets"])]


# This function uses the date_histogram with the extended_bounds
# Oddly the max part of the extended bounds doesnt seem to work unless the value is set to
# the string "now"...min works fine as 1970 or a number...
# NOTE:  These filters are specific to a user
def actor_histogram(actor_email_addr, start, end, interval="week"):
    tangelo.log('actor_histogram(%s, %s, %s, %s)' %(actor_email_addr, start, end, interval))
    return {
        "size":0,
        "aggs":{
            "sent_agg":{"filter" :
                {"bool":{
                    "should":[
                        {"term" : { "senders" : actor_email_addr}}
                    ],
                    "must":[{"range" : {"datetime" : { "gte": start, "lte": end }}}]
                }
                },

                "aggs" : {
                    "sent_emails_over_time" : {
                        "date_histogram" : {
                            "field" : "datetime",
                            "interval" : interval,
                            "format" : "yyyy-MM-dd",
                            "min_doc_count" : 0,
                            "extended_bounds":{
                                "min": start,
                                # "max" doesnt really work unless it's set to "now" 
                                "max": end
                            }
                        }
                    }
                }
            },
            "rcvr_agg":{"filter" : {"bool":{
                "should":[
                    {"term" : { "tos" : actor_email_addr}},
                    {"term" : { "ccs" : actor_email_addr}},
                    {"term" : { "bccs" : actor_email_addr}}

                ],
                "must":[{"range" : {"datetime" : { "gte": start, "lte": end }}}]
            }},

                "aggs" : {
                    "rcvd_emails_over_time" : {
                        "date_histogram" : {
                            "field" : "datetime",
                            "interval" : interval,
                            "format" : "yyyy-MM-dd",
                            "min_doc_count" : 0,
                            "extended_bounds":{
                                "min": start,
                                "max": end
                            }
                        }
                    }
                }
            }
        }
    }

def detect_activity(index, type, query_function, **kwargs):
    es = Elasticsearch()
    resp = es.search(index=index, doc_type=type, body=query_function(**kwargs))
    return resp["aggregations"]["filter_agg"]["emails_over_time"]["buckets"]

def get_total_daily_activity(index, type, query_function, **kwargs):
    es = Elasticsearch()
    resp = es.search(index=index, doc_type=type, body=query_function(**kwargs))
    return resp["aggregations"]["filter_agg"]["emails_over_time"]["buckets"]

# Returns a sorted map of
def get_email_activity(index, account_id, query_function, **kwargs):
    es = Elasticsearch()
    body = query_function(**kwargs)
    print body
    resp = es.search(index=index, doc_type="emails", request_cache="false", body=body)
    return [_map_activity(index, account_id, sent_rcvd) for sent_rcvd in zip(resp["aggregations"]["sent_agg"]["sent_emails_over_time"]["buckets"],
                                                                             resp["aggregations"]["rcvr_agg"]["rcvd_emails_over_time"]["buckets"])]
# Returns a sorted map of
def get_attachment_activity(index, account_id, query_function, **kwargs):
    es = Elasticsearch()
    resp = es.search(index=index, doc_type="attachments", request_cache="false", body=query_function(**kwargs))
    return [_map_attachments(index, account_id, attachments) for attachments in zip(resp["aggregations"]["attachments_filter_agg"]["attachments_over_time"]["buckets"])]

if __name__ == "__main__":
    # es = Elasticsearch()
    # body = entity_histogram_query(email_addrs=["jeb@jeb.org"], query_terms="", topic_score=None, date_bounds=("1970","now"), entity_agg_size=10)
    # print body
    # resp = es.search(index="sample", doc_type="emails",body=body)
    # res = get_entity_histogram("sample", "emails", email_addrs=[], query_terms="", topic_score=None, date_bounds=("2000","2002"))
    # print {"entities" : [[str(i), entity ["type"], entity ["key"], entity ["doc_count"]] for i,entity in enumerate(res)]}
    #
    # res = get_entity_histogram("sample", "emails", email_addrs=["oviedon@sso.org"], query_terms="", topic_score=None, date_bounds=("2000","2002"))
    # print res
    # res = get_attachment_activity("sample", account_id="", query_function=attachment_histogram, sender_email_addr="", start="1970", end="now", interval="year")
    # print res

    activity = get_email_activity("sample", "jeb@jeb.org", actor_histogram, actor_email_addr="jeb@jeb.org", start="2000", end="2002", interval="week")
    print activity
    # for s in res:
