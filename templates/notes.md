in the bus admin, train admin and flight admin dashboards where they add routes i want them to add the price for the route as it is not suppossed to be added on the schedules as it is now and the routes added can be later modified or deleted.in the bus admin dashboard only where the admin adds buses, the admin should also be able to add the number plate of the bus which should and a brief description which is optional, that description can also be added by the other admins for trains and flights and are visible to the passengers. the flight, bus and train admins can also edit the profile of their companies, add overall description of the company and other relevant details and also upload an image that is also visible to the passenger side. the passenger should also see the company of the mode of transport on their dashboard and when they search for a trip the filter should work perfectly
in the bus admin dashboard i have addbuses section, i want to update it so that the admin can also add delivery trucks the same way as he was adding passenger buses though without the seat simulation. in the train admin dashboard i have a section for adding trains i want the admin also to be able to add the cargo trucks the same way as he was adding the passenger trains though without seat simulation. also the flight admin dashboard in the section for adding the flights i want the admin to be able to add cargo flights the same way as he was adding passenger flights though without seat simulation. the added parcel and cargo vehicles should not appear to passengers while booking
i want the bus admin, flight admin, train admin and technical staff as they book or send cargo or parcels they are able to see the vehicles that they are suppossed to book. the technical staff should see the details related to their companies. both the admins and technical staffs are able to choose vehicles from their companies. if they want to book for the passengers seat simulation for the vehicles should also be available for them to choose from and be able to prompt the passenger or even the sender of the parcel for payment and a ticket be released. i want you to configure the stk push so that it doesnt just simulate and release tickets but to prompt the users as i will enter the sandbox and callback url in the .env file. also for the emails where the ticket is sent as i will enter the smtp details. in the homepage or index.html their is a subscribe option basically in the footer for any user of the system to subcribe by entering the email. i want if the user enters the email they should be visible to the system admin. so create a sidebar where these emails are seen by the system admin and the system admin can also send mails to the emails of the subscribers.
in the bus admin, train admin and flight admin, where they book for passengers, i want after entering the passengers details they should be able to search for a vehicle and select the seat for the passenger like in the technical staff dashboard, in the technical staff boarding control, he should be able to select the routes and the vehicles that the company has registered and be able to see the manifest of passengers who have already booked
most of the data when i press loyalty points are hardcoded and not dynamic, i want them to be dynamic and also the one showing in the sidebar is not dynamic from the database. correct them for me. also the stk push is still working as a simulator, when i press it it just generates the ticket without prompting the user. i want it to prompt the user first then generates the ticket and after that it sends the ticket to the user using email
i wnated the seat simulation to be modified by the bus admin as he adds the buses, train admin as he adds the trains and flight admin as he adds the flights not the system admin. and in the system admin section in the templates i want it to have a sidebar with all the links
i think the book and prompt button should not be there, let it be the same as the passengers, where after searching for the available trip you choose seat also and is when you prompt;, im getting this error currently in the terminal when i press the button ; [28/May/2026 07:13:35] "GET /technical-staff/ HTTP/1.1" 200 30861
[28/May/2026 07:13:38] "GET /technical-staff/booking-assist/ HTTP/1.1" 200 19332
[28/May/2026 07:13:47] "POST /technical-staff/booking-assist/ HTTP/1.1" 200 22881
Booking error: Cannot resolve keyword 'vehicle_number' into field. Choices are: available_seats, bookings, bus_number, company, company_id, description, driver, driver_id, id, is_cargo, normal_seats, number_plate, route, route_id, schedules, vip_seats
Traceback (most recent call last):
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\apps\technical_staff\views.py", line 185, in tech_booking_assist
    vehicle = Bus.objects.filter(company=company, vehicle_number=vehicle_name.split(' ')[-1]).first()
              ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\manager.py", line 87, in manager_method
    return getattr(self.get_queryset(), name)(*args, **kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\query.py", line 1495, in filter
    return self._filter_or_exclude(False, args, kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\query.py", line 1513, in _filter_or_exclude
    clone._filter_or_exclude_inplace(negate, args, kwargs)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\query.py", line 1523, in _filter_or_exclude_inplace
    self._query.add_q(Q(*args, **kwargs))
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\sql\query.py", line 1648, in add_q
    clause, _ = self._add_q(q_object, can_reuse)
                ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\sql\query.py", line 1680, in _add_q
    child_clause, needed_inner = self.build_filter(
                                 ~~~~~~~~~~~~~~~~~^
        child,
        ^^^^^^
    ...<7 lines>...
        update_join_types=update_join_types,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\sql\query.py", line 1528, in build_filter
    lookups, parts, reffed_expression = self.solve_lookup_type(arg, summarize)
                                        ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\sql\query.py", line 1335, in solve_lookup_type
    _, field, _, lookup_parts = self.names_to_path(lookup_splitted, self.get_meta())
                                ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Home\Documents\Brian's Project\smarttravels\venv\Lib\site-packages\django\db\models\sql\query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'vehicle_number' into field. Choices are: available_seats, bookings, bus_number, company, company_id, description, driver, driver_id, id, is_cargo, normal_seats, number_plate, route, route_id, schedules, vip_seats
[28/May/2026 07:13:58] "POST /technical-staff/booking-assist/ HTTP/1.1" 200 19416
