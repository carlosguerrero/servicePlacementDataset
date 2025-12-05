d1 = {
  "brand": "Ford",
  "model": "Mustang",
  "year": 1964
}

print("Hola")
print(d1["brand"])

a = 5
def scenario1():
    # sorted_events = sorted(events_list.items(), key=lambda item: item[1]['time'])
    global_time = 0
    prueba = 0
    while prueba < 3 or a != 5:
        print(prueba)

        # events_list.sort_by_time()
        # for event in sorted_events:
        #     global_time = event[1]['time']
        #     if event[1]['type_object'] == 'user':
        #         user_set = update_system_state(event, user_set)
        #     elif event[1]['type_object'] == 'app':
        #         application_set = update_system_state(event, application_set)
            
        #     print(f"Global Time: {global_time}")
        #     print(f"Users: {user_set}")
        prueba += 1

    pass

scenario1()