from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
import db
import generic_helper
app = FastAPI()

inprogess_orders = {}

@app.post("/")
async def handle_request(request:Request):
    payload = await request.json()

    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']
    
     
    it_contains_session_id_plus_extra_info = ""

    for context in output_contexts:
        if 'name' in context:
            it_constains_session_id_plus_extra_info = context['name']

    # extracting session_id
    session_id = generic_helper.extract_session_id(it_constains_session_id_plus_extra_info)
      
    intent_handler_dict = {
        'order.add - context: ongoing-order' : add_to_order,
        'order.complete - context: ongoing-order': complete_order,
        'order.remove - context: ongoing-order' :  remove_from_order,
        'track.order - context: ongoing-tracking' : track_order,
    }

    return intent_handler_dict[intent](parameters,session_id)


 

def complete_order(parameters,session_id):
    if session_id not in inprogess_orders:
        fulfillmentText = f"please place your order again. We have trouble in finding your order"
    else:
        order = inprogess_orders[session_id]
        order_id = save_to_db(order)

 
    if order_id == -1:
        fulfillmentText = "sorry,I couldn't process your order due to a backend error."\
                           "Please place a new order"
    else:
         order_total = db.get_total_order_price(order_id)
        
         fulfillmentText = f"Awesome. We have placed your order."\
                           f"Here is your order id # {order_id}."\
                           f"your order total is {order_total} which you can pay at time of delivery"

    # if order is complete and delivered then we have to remove it from queue
    del inprogess_orders[session_id]                         

    return JSONResponse(content = {
            "fulfillmentText" : fulfillmentText
        })

                        


def save_to_db(order):
    # order = {"pizza": 2, "chole": 1}
    next_order_id = db.get_next_order_id()

    for food_item, quantity in order.items():
        rcode = db.insert_order_item(
        food_item,
        quantity,
        next_order_id
    )

    if rcode == -1:
        return -1

    db.insert_order_tracking(next_order_id,"in progress")    

    return next_order_id



def add_to_order(parameters,session_id):
    food_items = parameters['food-item']
    quantities = parameters['number']

    if(len(food_items)!=len(quantities)):
        fulfillmentText = "sorry i didn't understood.Can you please specify food item and quantity"
    else:

        # {lassi,chai}, {1,2} = > {lassi:1},{chai,2}

        new_food_dict = dict(zip(food_items,quantities))

        if session_id in inprogess_orders:
            current_food_dict = inprogess_orders[session_id]
            current_food_dict.update(new_food_dict)
            inprogess_orders[session_id] = current_food_dict
        else:
            inprogess_orders[session_id] = new_food_dict

        order_Str = generic_helper.get_str_from_food_dict(inprogess_orders[session_id])
        fulfillmentText = f"So far you have: {order_Str}. Do you need anything else?" 

    return JSONResponse(content = {
            "fulfillmentText" : fulfillmentText
        })    


def track_order(parameters,session_id):

    # number = order_id
    order_id =  int(parameters['number'])

    status = db.get_order_status(order_id)
    if status:
        fulfillmentText = f"order_id is {order_id} and order_status is {status}"
    else:
         fulfillmentText = f"no order found with this  id {order_id}"   


    return JSONResponse(content = {
            "fulfillmentText" : fulfillmentText
        })

def remove_from_order(parameters,session_id):
    if session_id not in inprogess_orders:
        return JSONResponse(content={
            "fulfillmentText": "I'm having a trouble finding your order. Sorry! Can you  place a new order please?"
        })


    current_order = inprogess_orders[session_id]
    food_item = parameters["food-item"]

    removed_items = []
    not_such_items = []
    for item in food_item:
        if item not in current_order:
            not_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    if len(removed_items)>0:
        fulfillmentText = f"Removed {",".join(removed_items)} from your orders."

    if len(not_such_items)>0:
        fulfillmentText = f"No such  {",".join(not_such_items)} found in your orders"
    if len(current_order.keys())==0:
         fulfillmentText+="Your order is empty!"  
    else:
        order_str = generic_helper.get_str_from_food_dict(current_order)  
        fulfillmentText+=f"Here is what left in your order: {order_str}"  

    return JSONResponse(content = {
            "fulfillmentText" : fulfillmentText
        })      
