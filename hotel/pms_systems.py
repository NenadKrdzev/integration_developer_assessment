from abc import ABC, abstractmethod
import inspect
import sys
import json
import phonenumbers
from .models import Stay , Guest

from typing import Optional

from hotel.external_api import (
    get_reservations_between_dates,
    get_reservation_details,
    get_guest_details,
    APIError,
)

from hotel.models import Stay, Guest, Hotel


class PMS(ABC):
    """
    Abstract class for Property Management Systems.
    """

    def __init__(self):
        pass

    @property
    def name(self):
        longname = self.__class__.__name__
        return longname[4:]

    @abstractmethod
    def clean_webhook_payload(self, payload: str) -> dict:
        """
        Clean the json payload and return a usable dict.
        """
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, webhook_data: dict) -> bool:
        """
        This method is called when we receive a webhook from the PMS.
        Handle webhook handles the events and updates relevant models in the database.
        Requirements:
            - Now that the PMS has notified you about an update of a reservation, you need to
                get more details of this reservation. For this, you can use the mock API
                call get_reservation_details(reservation_id).
            - Handle the payload for the correct hotel.
            - Update or create a Stay.
            - Update or create Guest details.
        """
        raise NotImplementedError

    @abstractmethod
    def update_tomorrows_stays(self) -> bool:
        """
        This method is called every day at 00:00 to update the stays checking in tomorrow.
        Requirements:
            - Get all stays checking in tomorrow by calling the mock API
                get_reservations_between_dates(checkin_date, checkout_date).
            - Update or create the Stays.
            - Update or create Guest details. Deal with missing and incomplete data yourself
                as you see fit. Deal with the Language yourself. country != language.
        """
        raise NotImplementedError

    @abstractmethod
    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        """
        This method is called when we want to know if the stay includes breakfast.
        Notice that the breakfast data is not stored in any of the models?
        How would you deal with this?
        Requirements:
            - Your input is a Stay object.
            - Return True if the stay includes breakfast, otherwise False. Return None if
                you don't know.
        """
        raise NotImplementedError


class PMS_Mews(PMS):
    def clean_webhook_payload(self, payload: str) -> dict:
        # TODO: Implement the method
        try:
            cleaned_data=json.loads(payload);
            return cleaned_data;
        except json.JSONDecodeError as e:
            raise ValueError(f'Error decoding at {e}')
            return {}

    def handle_webhook(self, webhook_data: dict) -> bool:
        # TODO: Implement the method
        
        #Retrieve the id for the hotel and mapping it 
        id_hotel=webhook_data["HotelId"]
        try:
            #finding the hotel by Id
            hotel=Hotel.objects.get(pms_hotel_id=id_hotel)
            #Event cycle for the json in order to retrieve the reservation and guest details
            events=webhook_data["Events"]
            for event in events:
                res_id=event["Value"]["ReservationId"]
                res_details=self.clean_webhook_payload(get_reservation_details(res_id))
                guest_id=res_details["GuestId"]
                guest_details=self.clean_webhook_payload(get_guest_details(guest_id))

                #Updating or create a new stay with its respected fields
                stay, created = Stay.objects.update_or_create(
                            hotel=hotel,
                            pms_reservation_id=res_id,
                            pms_guest_id=guest_id,
                            defaults={
                                'checkin': res_details["CheckInDate"],
                                'checkout': res_details["CheckOutDate"],
                                'status': res_details["Status"],
                            }
                    )
                
                #Using the phonenumbers module to validate the phone number
                phone=guest_details["Phone"]
                validate_phone_number(phone)

                #Updating or create a new guest with its respected fields
                guest, created = Guest.objects.update_or_create(
                        phone=phone,
                        defaults={
                            'name':guest_details["Name"],
                        }
                    )
                #Saving the changes
                stay.guest=guest
                stay.save()
        except APIError as err:
            print(f"Api error at {err}") 
        return True

    def update_tomorrows_stays(self) -> bool:
        # TODO: Implement the method
        return True

    def stay_has_breakfast(self, stay: Stay) -> Optional[bool]:
        # TODO: Implement the method
        reservation_id=stay.pms_reservation_id
        try:
             res_details=self.clean_webhook_payload(get_reservation_details(reservation_id))
             return res_details["BreakfastIncluded"]
        except APIError as err:
            print(f"Api error at {err}")
   

def get_pms(name):
    fullname = "PMS_" + name.capitalize()
    # find all class names in this module
    # from https://stackoverflow.com/questions/1796180/
    current_module = sys.modules[__name__]
    clsnames = [x[0] for x in inspect.getmembers(current_module, inspect.isclass)]

    # if we have a PMS class for the given name, return an instance of it
    return getattr(current_module, fullname)() if fullname in clsnames else False

#Installed a module in order to validate the phone number
def validate_phone_number(phone_number):
    try:
        parsed_number=phonenumbers.parse(phone_number,None)

        is_valid = phonenumbers.is_valid_number(parsed_number)
        return is_valid
    except phonenumbers.NumberParseException:
        return False