'''
See https://www.usps.com/business/web-tools-apis/Address-Information-v3-2.htm for complete documentation of the API
'''

import json
import xmltodict as XTD
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from lxml import etree as ET

def utf8urlencode(data):
    ret = dict()
    for key, value in data.items():
        try:
            ret[key] = value.encode('utf8')
        except AttributeError:
            ret[key] = value
    return urlencode(ret).encode('utf8')


def dicttoxml(dictionary, parent, tagname, attributes=None):
    element = ET.SubElement(parent, tagname)
    if attributes: #USPS likes things in a certain order!
        for key in attributes:
            if key in dictionary:
                ET.SubElement(element, key).text = str(dictionary.get(key, ''))
    else:
        for key, value in dictionary.items():
            ET.SubElement(element, key).text = value
    return element


def xmltodict(element):
    ret = dict()
    for item in element.getchildren():
        ret[item.tag] = item.text
    return ret


class USPSXMLError(Exception):
    def __init__(self, element):
        self.info = xmltodict(element)
        super(USPSXMLError, self).__init__(self.info['Description'])


class USPSService(object):
    SERVICE_NAME = None
    API = None
    CHILD_XML_NAME = None
    PARAMETERS = None

    def __init__(self, url='https://secure.shippingapis.com/ShippingAPI.dll'):
        self.url = url

    def submit_xml(self, xml):
        data = {'XML': ET.tostring(xml),
                'API': self.API}
        response = urlopen(self.url, utf8urlencode(data))
        root = ET.parse(response).getroot()
        if root.tag == 'Error':
            raise USPSXMLError(root)
        error = root.find('.//Error')
        if error is not None:
            raise USPSXMLError(error)
        return root

    @staticmethod
    def parse_xml(xml):
        items = list()
        for item in xml.getchildren():
            items.append(xmltodict(item))
        return items


    def execute(self, userid, object_dicts):
        xml = self.make_xml(userid, object_dicts)
        return self.parse_xml(self.submit_xml(xml))

    def to_json(self, xml):
        return_dict = XTD.parse(ET.tostring(xml))
        return json.loads(json.dumps(return_dict))


class Address(USPSService):
    """ Base Address class.


    Address Formating Information from the USPS.

    FirmName - Name of Business (XYZ Corp.) [Optional]
    Address1 - Apartment or Suite number. [Optional]
    Address2 - Street Address [Required]
    City [Required]
    State - Abbreviation (CO) [Required]
    Zip5 - 5 Digit Zip Code [Required]
    Zip4 - 4 Digit Zip Code [Optional]

    This method will return a dictionary of values back from the USPS API.  The FullZip value
    is computed.

    {'City': 'Loveland', 'Address2': '500 E 3Rd St', 'State': 'CO', 'FullZip': '80537-5773', 'Zip5': '80537', 'Zip4': '5773'}

    To call:

    from usps.addressinformation import *


    address_validation = Address(user_id='YOUR_USER_ID')
    response = address_validation.validate(address1='500 E. third st', city='Loveland', state='CO')

    If an address is invalid (Doesn't exist) will raise USPSXMLError

    """
    SERVICE_NAME = 'AddressValidate'
    CHILD_XML_NAME = 'Address'
    API = 'Verify'
    USER_ID = ''
    PARAMETERS = ['FirmName',
                  'Address1',
                  'Address2',
                  'City',
                  'State',
                  'Zip5',
                  'Zip4']

    def __init__(self, user_id, *args, **kwargs):
        super(Address, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def format_response(self, address_dict, title_case):
        """ Format the response with title case.  Ensures
        that the address is "Human Readable"
        """

        if title_case:
            if 'Address1' in address_dict:
                address_dict['Address1'] = address_dict['Address1'].title()

            if 'FirmName' in address_dict:
                address_dict['FirmName'] = address_dict['FirmName'].title()

            address_dict['Address2'] = address_dict['Address2'].title()
            address_dict['City'] = address_dict['City'].title()
        if address_dict['Zip4']:
            address_dict['FullZip'] = "%s-%s" % (
                address_dict['Zip5'], address_dict['Zip4'])
        else:
            address_dict['FullZip'] = address_dict['Zip5']

        return address_dict

    def validate(self, firm_name='', address1='', address2='', city='', state='', zip_5='', zip_4='',
                 title_case=False):
        """ Validate provides a cleaner more verbose way to call the API.
        Repackages the attributes
        """
        address_dict = {'FirmName': firm_name,
                        'Address1': address1,
                        'Address2': address2,
                        'City': city,
                        'State': state,
                        'Zip5': zip_5,
                        'Zip4': zip_4}

        valid_address = self.execute(self.USER_ID, [address_dict])
        return self.format_response(valid_address[0], title_case)

    def make_xml(self, userid, addresses):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = userid
        index = 0
        for address_dict in addresses:
            address_xml = dicttoxml(address_dict, root, self.CHILD_XML_NAME, self.PARAMETERS)
            address_xml.attrib['ID'] = str(index)
            index += 1
        return root


#######################Rate API #############################################################

class DomesticRate(USPSService):

    SERVICE_NAME = 'RateV4'
    API = 'RateV4'
    USER_ID = ''
    PACKAGE_CHILD_XML_NAME = 'Package'
    PACKAGE_PARAMETERS = ['Service',           # required
                          'FirstClassMailType',# optional   # Required when Service == FIRST CLASS or FISRT CLASS COMMERICAL or FIRST CLASS HFP COMMERCIAL
                          'ZipOrigination',    # required
                          'ZipDestination',    # required
                          'Pounds',            # required
                          'Ounces',            # required
                          'Container',         # required
                          'Size',              # required
                          'Width',             # optional
                          'Length',            # optional
                          'Height',            # optional
                          'Girth',             # optional
                          'Value',             # optional
                          'AmountToCollect',   # optional
                          # 'SpecialServices', # object  # optional
                          # 'Content',         # object  # optional
                          'GroundOnly',        # optional
                          'SortBy',            # optional
                          'Machinable',        # optional
                          'ReturnLocations',   # optional
                          'ReturnServiceInfo', # optional
                          'DropOffTime',       # optional
                          'ShipDate']          # optional
    SPECIAL_SERVICE_CHILD_XML_NAME = 'SpecialServices'
    SPECIAL_SERVICE_PARAMETERS = ['SpecialService']

    CONTENT_CHILD_XML_NAME = 'Content'
    CONTENT_PARAMETERS = ['ContentType',
                          'ContentDescription']

    def __init__(self, user_id, *args, **kwargs):
        super(DomesticRate, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, package_dicts):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        ET.SubElement(root, "Revision").text = str(2)
        index = 0
        for package_dict in package_dicts:
            package_xml = dicttoxml(package_dict, root, self.PACKAGE_CHILD_XML_NAME, self.PACKAGE_PARAMETERS)

            # multiple special services
            if package_dict.get(self.SPECIAL_SERVICE_CHILD_XML_NAME):
                element = ET.SubElement(package_xml, self.SPECIAL_SERVICE_CHILD_XML_NAME)
                for special_service in package_dict.get(self.SPECIAL_SERVICE_CHILD_XML_NAME):
                    for key in self.SPECIAL_SERVICE_PARAMETERS:
                        if key in special_service:
                            ET.SubElement(element, key).text = str(special_service.get(key, ''))

            # content is not an array. only one as child xml
            if package_dict.get(self.CONTENT_CHILD_XML_NAME):
                content = package_dict.get(self.CONTENT_CHILD_XML_NAME)
                content_xml = dicttoxml(content, package_xml, self.CONTENT_CHILD_XML_NAME, self.CONTENT_PARAMETERS)

            package_xml.attrib['ID'] = str(index)
            index += 1
        return root

class IntlRateV2(USPSService):
    SERVICE_NAME = "IntlRateV2"
    API = "IntlRateV2"
    USER_ID = ""
    PACKAGE_CHILD_XML_NAME = 'Package'
    PACKAGE_PARAMETERS = [
        'Pounds',  # required
        'Ounces',  # required
        'MailType',  # required ,same as service in domestic
        'Machinable',  # optional
        # 'GXG'              #optinal
        'ValueOfContents',  # required
        'Country',  # required
        'Container',  # required
        'Size',  # required
        'Width',  # optional
        'Length',  # optional
        'Height',  # optional
        'Girth',  # optional
        'OriginZip',  # optional
        'CommercialFlag',  # optional
        'CommercialPlusFlag',  # optional
        # 'ExtraServices', # object  # optional
        # 'Content',         # object  # optional
        'AcceptanceDateTime',  # optional
        'DestinationPostalCode',  # optional
    ]

    GXG_CHILD_XML_NAME = 'GXG'
    GXG_PARAMETERS = ['POBoxFlag', 'GiftFlag']

    EXTRA_SERVICE_CHILD_XML_NAME = 'ExtraServices'
    EXTRA_SERVICE_PARAMETERS = ['ExtraService']

    CONTENT_CHILD_XML_NAME = 'Content'
    CONTENT_PARAMETERS = ['ContentType',
                          'ContentDescription']

    def __init__(self, user_id, *args, **kwargs):
        super(IntlRateV2, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, package_dicts):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        ET.SubElement(root, "Revision").text = str(2)
        index = 0
        for package_dict in package_dicts:
            package_xml = dicttoxml(package_dict, root, self.PACKAGE_CHILD_XML_NAME, self.PACKAGE_PARAMETERS)

            # multiple special services
            if package_dict.get(self.EXTRA_SERVICE_CHILD_XML_NAME):
                element = ET.SubElement(package_xml, self.EXTRA_SERVICE_CHILD_XML_NAME)
                for special_service in package_dict.get(self.EXTRA_SERVICE_CHILD_XML_NAME):
                    for key in self.EXTRA_SERVICE_PARAMETERS:
                        if key in special_service:
                            ET.SubElement(element, key).text = str(special_service.get(key, ''))

            # content is not an array. only one as child xml
            if package_dict.get(self.CONTENT_CHILD_XML_NAME):
                content = package_dict.get(self.CONTENT_CHILD_XML_NAME)
                content_xml = dicttoxml(content, package_xml, self.CONTENT_CHILD_XML_NAME, self.CONTENT_PARAMETERS)

            if package_dict.get(self.GXG_CHILD_XML_NAME):
                content = package_dict.get(self.GXG_CHILD_XML_NAME)
                content_xml = dicttoxml(content, package_xml, self.GXG_CHILD_XML_NAME, self.GXG_PARAMETERS)

            package_xml.attrib['ID'] = str(index)
            index += 1
        return root


############################################### TRACK API ############################################################

class Track(USPSService):
    SERVICE_NAME = 'Track'
    API = 'TrackV2'
    USER_ID = ''
    TRACK_CHILD_XML_NAME = 'TrackID'
    TRACK_PARAMETERS = []

    def __init__(self, user_id, *args, **kwargs):
        super(Track, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, tracker_ids):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        for tracker in tracker_ids:
            element = ET.SubElement(root, self.TRACK_CHILD_XML_NAME)
            element.attrib['ID'] = tracker
        return root



######################## PACKAGE PICKUP API ###########################


class CarrierPickupAvailability(USPSService):
    SERVICE_NAME = 'CarrierPickupAvailability'
    API = 'CarrierPickupAvailability'
    USER_ID = ''
    CARRIER_PICKUP_AVAILABILITY_PARAMETERS = ['FirmName',
                                              'SuiteOrApt',
                                              'Address2',
                                              'Urbanization',
                                              'City',
                                              'State',
                                              'ZIP5',
                                              'ZIP4',
                                              'Date']

    def __init__(self, user_id, *args, **kwargs):
        super(CarrierPickupAvailability, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, pickup_availability_dict):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        for key, value in pickup_availability_dict.items():
            if key in self.CARRIER_PICKUP_AVAILABILITY_PARAMETERS:
                ET.SubElement(root, key).text = value
        return root


class CarrierPickupSchedule(USPSService):
    SERVICE_NAME = 'CarrierPickupSchedule'
    API = "CarrierPickupSchedule"
    USER_ID = ''
    CARRIER_PICKUP_SCHEDULE = ["FirstName",
                               "LastName",
                               "FirmName",
                               "SuiteOrApt",
                               "Address2",
                               "Urbanization",
                               "City",
                               "State",
                               "ZIP5",
                               "ZIP4",
                               "Phone",
                               "Extension",
                               "EstimatedWeight",
                               "PackageLocation",
                               "SpecialInstructions",
                               "EmailAddress"]

    CARRIER_PICKUP_SCHEDULE_PACKAGE=["ServiceType","Count"]
    PACKAGE_KEY = "Package"
    def __init__(self, user_id, *args, **kwargs):
        super(CarrierPickupSchedule, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, pickup_schedule_dict):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        if self.PACKAGE_KEY not in pickup_schedule_dict:
            print("Package is needed")
            return
        for key, value in pickup_schedule_dict.items():
            if key in self.CARRIER_PICKUP_SCHEDULE:
                ET.SubElement(root, key).text = value

        for package_item_dict in pickup_schedule_dict.get('Package'):
            dicttoxml(package_item_dict, root, self.PACKAGE_KEY, self.CARRIER_PICKUP_SCHEDULE_PACKAGE)
        return root


class CarrierPickupCancel(USPSService):
    SERVICE_NAME = 'CarrierPickupCancel'
    API = 'CarrierPickupCancel'
    USER_ID = ''
    CARRIER_PICKUP_CANCEL_PARAMETERS= ['FirmName',
                                              'SuiteOrApt',
                                              'Address2',
                                              'Urbanization',
                                              'City',
                                              'State',
                                              'ZIP5',
                                              'ZIP4',
                                              'ConfirmationNumber']

    def __init__(self, user_id, *args, **kwargs):
        super(CarrierPickupCancel, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, pickup_cancel_dict):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        for key, value in pickup_cancel_dict.items():
            if key in self.CARRIER_PICKUP_CANCEL_PARAMETERS:
                ET.SubElement(root, key).text = value
        return root


class CarrierPickupChange(USPSService):
    SERVICE_NAME = "CarrierPickupChange"
    API = "CarrierPickupChange"
    USER_ID = ''
    CARRIER_PICKUP_SCHEDULE = ["FirstName",
                               "LastName",
                               "FirmName",
                               "SuiteOrApt",
                               "Address2",
                               "Urbanization",
                               "City",
                               "State",
                               "ZIP5",
                               "ZIP4",
                               "Phone",
                               "Extension",
                               "EstimatedWeight",
                               "PackageLocation",
                               "SpecialInstructions",
                               "ConfirmationNumber",
                               "EmailAddress"]

    CARRIER_PICKUP_SCHEDULE_PACKAGE = ["ServiceType", "Count"]
    PACKAGE_KEY = "Package"

    def __init__(self, user_id, *args, **kwargs):
        super(CarrierPickupChange, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, pickup_schedule_change_dict):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        if self.PACKAGE_KEY not in pickup_schedule_change_dict:
            print("Package is needed")
            return
        for key, value in pickup_schedule_change_dict.items():
            if key in self.CARRIER_PICKUP_SCHEDULE:
                ET.SubElement(root, key).text = value

        for package_item_dict in pickup_schedule_change_dict.get('Package'):
            dicttoxml(package_item_dict, root, self.PACKAGE_KEY, self.CARRIER_PICKUP_SCHEDULE_PACKAGE)
        return root


class CarrierPickupInquiry(USPSService):
    SERVICE_NAME = 'CarrierPickupInquiry'
    API = 'CarrierPickupInquiry'
    USER_ID = ''
    CARRIER_PICKUP_CANCEL_PARAMETERS = ['FirmName',
                                        'SuiteOrApt',
                                        'Address2',
                                        'Urbanization',
                                        'City',
                                        'State',
                                        'ZIP5',
                                        'ZIP4',
                                        'ConfirmationNumber']

    def __init__(self, user_id, *args, **kwargs):
        super(CarrierPickupInquiry, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, pickup_inquiry_dict):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        for key, value in pickup_inquiry_dict.items():
            if key in self.CARRIER_PICKUP_CANCEL_PARAMETERS:
                ET.SubElement(root, key).text = value
        return root


################################# Service Standard Service ################################

class MailService(USPSService):
    SERVICE_NAME = ['PriorityMail', 'StandardB', 'FirstClassMail', 'ExpressMailCommitment']
    API = SERVICE_NAME
    MAIL_SERVICE_PARAMETERS = ['OriginZip', 'DestinationZip', 'DestinationType']
    MAIL_SERVICE_PRIORITY_PARAMETERS = MAIL_SERVICE_PARAMETERS + ['PMGuarantee', 'ClientType']
    MAIL_SERVICE_STANDARDB_PARAMETERS = MAIL_SERVICE_PARAMETERS + ['ClientType']
    MAIL_SERVICE_FIRSTCLASS_PARAMETERS = MAIL_SERVICE_PARAMETERS
    MAIL_SERVICE_EXPRESS_PARAMETERS = ['OriginZip', 'DestinationZip', 'Date', 'DropOffTime' 'PMGuarantee', 'ReturnDates']

    def __init__(self, user_id, *args, **kwargs):
        super(MailService, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, mail_service_dict, service_name):
        if service_name in self.SERVICE_NAME:
            root = ET.Element(service_name + 'Request')
            root.attrib['USERID'] = self.USER_ID
            for key, value in mail_service_dict.items():
                if service_name is 'ExpressMailCommitment':
                    parameters = self.MAIL_SERVICE_EXPRESS_PARAMETERS
                elif service_name is 'PriorityMail':
                    parameters = self.MAIL_SERVICE_PRIORITY_PARAMETERS
                elif service_name is 'StandardB':
                    parameters = self.MAIL_SERVICE_STANDARDB_PARAMETERS
                elif service_name is 'FirstClassMail':
                    parameters = self.MAIL_SERVICE_FIRSTCLASS_PARAMETERS
                else:
                    parameters = self.MAIL_SERVICE_PARAMETERS

                if key in parameters:
                    ET.SubElement(root, key).text = value
            return root

class ServiceDelivery(USPSService):
    SERVICE_NAME = 'SDCGetLocations'
    API = SERVICE_NAME

    SERVICE_DELIVERY_PARAMETERS = [
        "MailClass",
        "OriginZIP",
        "DestinationZIP",
        "AcceptDate",
        "AcceptTime",
        "NonEMDetail",
        "NonEMOriginType",
        "NonEMDestType",
        "Weight",
        "ClientType"]

    def __init__(self, user_id, *args, **kwargs):
        super(ServiceDelivery, self).__init__(*args, **kwargs)
        self.USER_ID = user_id

    def make_xml(self, sdc_get_location_dict):
        root = ET.Element(self.SERVICE_NAME + 'Request')
        root.attrib['USERID'] = self.USER_ID
        for key, value in sdc_get_location_dict.items():
            if key in self.SERVICE_DELIVERY_PARAMETERS:
                ET.SubElement(root, key).text = value
        return root
